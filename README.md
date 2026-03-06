# pgx-mysql-migration-demo

本项目是 Django 多数据库目标演示工程，可通过 `DB_TARGET` 切换：
- `mysql`
- `pgx`
- `pg`

## 一次性准备（Windows）

```powershell
# 1) 进入项目目录
cd pgx-mysql-migration-demo

# 2) 创建虚拟环境（首次执行）
python -m venv .venv

# 3) 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 4) 安装依赖
pip install -r requirements.txt

# 5) 复制环境变量模板（首次执行）
Copy-Item .env.example .env
```

## 启动项目

```powershell
# 方式一：已激活虚拟环境时
python manage.py runserver 0.0.0.0:8000

# 方式二：未激活虚拟环境时（推荐直接指定解释器）
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

启动后访问：
- `http://127.0.0.1:8000/healthz`
- `http://127.0.0.1:8000/demo/txns`
- `http://127.0.0.1:8000/demo/customers`
- `http://127.0.0.1:8000/demo/risk`

## 停止项目

```powershell
# 方式一：前台运行时，直接按 Ctrl + C

# 方式二：后台运行时，先查端口对应 PID，再结束进程
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## 启动前建议执行

```powershell
# 首次或模型变更后，先执行迁移
python manage.py migrate

# 可选：做配置检查
python manage.py check
```

## 功能运行流程（按功能）

### 1) 系统启动与数据库预检查流程

1. 执行 `python manage.py runserver 0.0.0.0:8000`。
2. `manage.py` 会先调用 `demo_project/db_bootstrap.py`。
3. 按 `.env` 中 `DB_TARGET` 选择目标库（`mysql/pgx/pg`）。
4. 检查目标数据库是否存在：
   - 存在：继续启动 Django。
   - 不存在：自动创建数据库并尝试授权。
5. 启动日志写入 `log/bootstrap.log`，应用日志写入 `log/app.log`。

### 2) 健康检查流程（`/healthz`）

1. 访问 `http://127.0.0.1:8000/healthz`。
2. 系统读取当前 `DB_TARGET`。
3. 执行数据库探活 SQL：`SELECT 1`。
4. 返回 JSON：
   - 成功：`status=ok`、`db_target`、`select_1=1`。
   - 失败：`status=error` 并返回错误信息。

### 3) 客户演示页流程（`/demo/customers`）

1. 页面读取筛选参数（`status/mobile/account_status/offset/count`）。
2. 从 `banktel/sql/customers.sql` 读取命名 SQL 模板。
3. 按当前 `DB_TARGET` 执行 SQL，并记录审计信息。
4. 页面展示四块内容：
   - 筛选参数
   - 原始 SQL
   - 最终执行 SQL
   - 结果表格
5. 关键演示点：`<=>` 空值等价筛选。

### 4) 交易作战台流程（`/demo/txns`）

1. 页面读取交易筛选参数（`customer_no/status/start_at/end_at/offset/count`）。
2. 执行 `banktel/sql/txns.sql` 对应查询，展示交易结果表。
3. 同时加载交易待办列表（`Txn`）、当前交易详情、关联风险案件。
4. 根据登录用户组决定可见按钮：
   - `txn_maker`：`submit-review/book/clear/ack`
   - `txn_checker`：`approve/reject`
5. 点击按钮后触发 POST 接口并执行状态机流转。

### 5) 交易动作流转与风控联动流程

1. 交易状态机：
   - `RECEIVED -> REVIEW_PENDING -> APPROVED -> BOOKED -> CLEARED -> ACKED`
   - 分支：`REVIEW_PENDING -> REJECTED`
2. 角色校验：
   - 未登录：拒绝。
   - 无组权限：返回 403。
   - 状态非法跳转：返回 400。
3. 风险联动（同客户+账户的未闭环风险单）：
   - `submit-review`：`OPEN -> REVIEWING`
   - `reject`：`OPEN/REVIEWING -> BLOCKED`
   - `clear`：`REVIEWING -> RELEASED`
   - `ack`：`RELEASED -> CLOSED`
4. 联动结果写入 `linked_txn_no/reviewed_by/reviewed_at`，并记录到日志。

### 6) 风险演示页流程（`/demo/risk`）

1. 页面读取筛选参数（`status/min_amount/offset/count`）。
2. 从 `banktel/sql/risk.sql` 读取并执行命名 SQL。
3. 展示风险状态、关联交易号、风险金额等结果字段。
4. 关键演示点：`&&` 与 `!` 过滤表达式、`manual_close` 规则过滤。

### 7) 仿真数据导入流程（`seed_demo_data`）

1. 执行 `python manage.py seed_demo_data --scale medium --reset`。
2. 创建/更新演示用户与权限组。
3. 按规模写入或更新 Customer/Account/Txn/RiskCase/Cdr/BillMonthly。
4. 命令输出每类数据的 `created/updated` 统计，二次执行不重复膨胀（幂等）。
5. 导入后即可直接访问 `/demo/*` 页面进行论文演示。

### 8) 管理后台流程（`/admin`）

1. 用管理员账号登录 Django Admin。
2. 查看并维护 6 个核心模型：
   - `Customer`、`Account`、`Txn`、`Cdr`、`BillMonthly`、`RiskCase`
3. 通过 `list_display/search/filter` 对数据进行核对和抽样检查。

### 9) 日志与问题排查流程

1. 启动与数据库检查：`log/bootstrap.log`
2. 应用与交易流转：`log/app.log`
3. SQL 执行审计：`log/sql.log`
4. 访问日志：`log/access.log`
5. PGX 场景下，执行 MySQL 方言前会先有 `SET mysql_mode=true;` 审计记录。

## 注意事项

1. 不要把真实密码写入代码，数据库密码仅放在 `.env`。
2. `DB_TARGET` 必须是 `mysql`、`pgx`、`pg` 之一。
3. 运行管理命令时会触发数据库存在性检查（见 `demo_project/db_bootstrap.py`）。
4. 当 `DB_TARGET=pgx` 且执行 MySQL 方言 SQL 时，会先执行 `SET mysql_mode=true;`。
5. 日志目录在 `log/`，重点查看：
   - `log/bootstrap.log`
   - `log/app.log`
   - `log/sql.log`
   - `log/access.log`
6. 如端口 `8000` 被占用，可改为其他端口（如 `8001`）：
   `python manage.py runserver 0.0.0.0:8001`

## 仿真数据初始化（论文演示）

### 导入命令

```powershell
# 默认导入 medium 规模（推荐）
python manage.py seed_demo_data

# 指定规模
python manage.py seed_demo_data --scale small
python manage.py seed_demo_data --scale medium
python manage.py seed_demo_data --scale large

# 导入前清理已有 DEMO 前缀数据
python manage.py seed_demo_data --scale medium --reset

# 指定演示账号密码
python manage.py seed_demo_data --password Demo@123456
```

### 导入后默认演示账号

- `demo_admin`
- `demo_maker_01`
- `demo_maker_02`
- `demo_checker_01`
- `demo_viewer_01`

默认密码：`Demo@123456`（可通过 `--password` 修改）

### 推荐演示筛选参数（1-2页数据）

1. `/demo/txns`
- 默认参数直接查询（约 30+ 条）
- 或设置：`status=REVIEW_PENDING`，`start_at=<近7天>`

2. `/demo/customers`
- `query=customers_null_eq_list`
- `status=ACTIVE`
- `mobile` 留空（匹配 `NULL`）

3. `/demo/risk`
- `query=risk_active_cases`
- `status` 留空
- `min_amount=0`

### 业务场景说明（正常银行对公流程）

- 场景A：对公供应商付款（主流程）
- 场景B：工资代发批次（批量转账）
- 场景C：日常费用结算（低风险稳定）
- 场景D：复核拒绝分支（流程异常闭环）

### 真实业务参考来源（论文可引用）

1. Maker-Checker 授权分离（Oracle FLEXCUBE）
- https://docs.oracle.com/en/industries/financial-services/flexcube-investor-servicing/14.7.6.0.0/txnis/transactions-user-guide.pdf
- https://docs.oracle.com/cd/F56379_01/html/LN/LN05_Cont.htm

2. 企业网银指令状态（工行）
- https://www.icbc.com.cn/icbc/html/view/111112/html/10/04.htm

3. 对公转账与回单查询（中行）
- https://www.boc.cn/ebanking/service/cs1/202207/t20220711_21411224.html

4. 批量转账文件上传（中行）
- https://www.boc.cn/au/custserv/cs2/201712/t20171221_10961065.html

5. 支付结算与风险治理（人民银行公开材料）
- https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025092212544083008/index.html
- https://www.pbc.gov.cn/goutongjiaoliu/113456/113475/f8b4e124846b4e7e86a9b2ad6e0bbb0f/index.html
