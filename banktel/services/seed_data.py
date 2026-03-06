from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone

from banktel.models import (
    Account,
    BillMonthly,
    Cdr,
    Customer,
    RiskCase,
    RiskPhase,
    Txn,
    TxnCorePhase,
)

SCALE_CONFIG = {
    "small": {
        "customers": 20,
        "accounts": 16,
        "txns": 22,
        "risk_cases": 16,
        "cdrs": 16,
        "bills": 16,
    },
    "medium": {
        "customers": 30,
        "accounts": 24,
        "txns": 34,
        "risk_cases": 26,
        "cdrs": 24,
        "bills": 24,
    },
    "large": {
        "customers": 45,
        "accounts": 36,
        "txns": 52,
        "risk_cases": 40,
        "cdrs": 36,
        "bills": 36,
    },
}

DEMO_CUSTOMER_PREFIX = "CUST-DEMO-"
DEMO_ACCOUNT_PREFIX = "ACC-DEMO-"
DEMO_TXN_PREFIX = "TXN-DEMO-"
DEMO_RISK_PREFIX = "RISK-DEMO-"
DEMO_CDR_PREFIX = "CDR-DEMO-"
DEMO_USERNAMES = [
    "demo_admin",
    "demo_maker_01",
    "demo_maker_02",
    "demo_checker_01",
    "demo_viewer_01",
]


def seed_demo_data(
    *,
    scale: str = "medium",
    reset: bool = False,
    password: str = "Demo@123456",
) -> dict[str, Any]:
    if scale not in SCALE_CONFIG:
        raise ValueError(f"Unsupported scale: {scale}")

    summary: dict[str, Any] = {
        "scale": scale,
        "deleted": {},
        "groups": {"created": 0, "updated": 0},
        "users": {"created": 0, "updated": 0},
        "customers": {"created": 0, "updated": 0},
        "accounts": {"created": 0, "updated": 0},
        "txns": {"created": 0, "updated": 0},
        "risk_cases": {"created": 0, "updated": 0},
        "cdrs": {"created": 0, "updated": 0},
        "bills": {"created": 0, "updated": 0},
    }

    with transaction.atomic():
        users = _seed_users(summary=summary, password=password)

        if reset:
            _reset_demo_data(summary=summary)

        customers = _seed_customers(scale=scale, summary=summary)
        accounts = _seed_accounts(scale=scale, customers=customers, summary=summary)
        txns = _seed_txns(
            scale=scale,
            customers=customers,
            accounts=accounts,
            users=users,
            summary=summary,
        )
        _seed_risk_cases(
            scale=scale,
            customers=customers,
            accounts=accounts,
            txns=txns,
            users=users,
            summary=summary,
        )
        _seed_cdrs(scale=scale, customers=customers, accounts=accounts, summary=summary)
        _seed_bills(scale=scale, accounts=accounts, summary=summary)

    return summary


def _record_upsert(summary: dict[str, Any], key: str, created: bool) -> None:
    item = summary[key]
    if created:
        item["created"] += 1
    else:
        item["updated"] += 1


def _record_deleted(summary: dict[str, Any], key: str, count: int) -> None:
    summary["deleted"][key] = int(count)


def _upsert(
    *,
    model,
    lookup: dict[str, Any],
    defaults: dict[str, Any],
    summary: dict[str, Any],
    summary_key: str,
):
    obj, created = model.objects.update_or_create(defaults=defaults, **lookup)
    _record_upsert(summary, summary_key, created)
    return obj


def _seed_users(*, summary: dict[str, Any], password: str) -> dict[str, User]:
    maker_group, created = Group.objects.get_or_create(name="txn_maker")
    _record_upsert(summary, "groups", created)
    checker_group, created = Group.objects.get_or_create(name="txn_checker")
    _record_upsert(summary, "groups", created)

    users: dict[str, User] = {}

    users["admin"] = _upsert_user(
        summary=summary,
        username="demo_admin",
        password=password,
        defaults={
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
            "email": "demo_admin@example.com",
        },
    )
    users["maker_01"] = _upsert_user(
        summary=summary,
        username="demo_maker_01",
        password=password,
        defaults={
            "is_staff": True,
            "is_superuser": False,
            "is_active": True,
            "email": "demo_maker_01@example.com",
        },
    )
    users["maker_02"] = _upsert_user(
        summary=summary,
        username="demo_maker_02",
        password=password,
        defaults={
            "is_staff": True,
            "is_superuser": False,
            "is_active": True,
            "email": "demo_maker_02@example.com",
        },
    )
    users["checker_01"] = _upsert_user(
        summary=summary,
        username="demo_checker_01",
        password=password,
        defaults={
            "is_staff": True,
            "is_superuser": False,
            "is_active": True,
            "email": "demo_checker_01@example.com",
        },
    )
    users["viewer_01"] = _upsert_user(
        summary=summary,
        username="demo_viewer_01",
        password=password,
        defaults={
            "is_staff": True,
            "is_superuser": False,
            "is_active": True,
            "email": "demo_viewer_01@example.com",
        },
    )

    users["maker_01"].groups.set([maker_group])
    users["maker_02"].groups.set([maker_group])
    users["checker_01"].groups.set([checker_group])
    users["viewer_01"].groups.clear()

    return users


def _upsert_user(
    *,
    summary: dict[str, Any],
    username: str,
    password: str,
    defaults: dict[str, Any],
) -> User:
    user, created = User.objects.get_or_create(username=username, defaults=defaults)
    if not created:
        changed = False
        for key, value in defaults.items():
            if getattr(user, key) != value:
                setattr(user, key, value)
                changed = True
        if changed:
            user.save(update_fields=list(defaults.keys()))

    user.set_password(password)
    user.save(update_fields=["password"])
    _record_upsert(summary, "users", created)
    return user


def _reset_demo_data(*, summary: dict[str, Any]) -> None:
    deleted = BillMonthly.objects.filter(
        customer__customer_no__startswith=DEMO_CUSTOMER_PREFIX
    ).delete()[0]
    _record_deleted(summary, "bills", deleted)

    deleted = Cdr.objects.filter(customer__customer_no__startswith=DEMO_CUSTOMER_PREFIX).delete()[0]
    _record_deleted(summary, "cdrs", deleted)

    deleted = RiskCase.objects.filter(
        customer__customer_no__startswith=DEMO_CUSTOMER_PREFIX
    ).delete()[0]
    _record_deleted(summary, "risk_cases", deleted)

    deleted = Txn.objects.filter(customer__customer_no__startswith=DEMO_CUSTOMER_PREFIX).delete()[0]
    _record_deleted(summary, "txns", deleted)

    deleted = Account.objects.filter(account_no__startswith=DEMO_ACCOUNT_PREFIX).delete()[0]
    _record_deleted(summary, "accounts", deleted)

    deleted = Customer.objects.filter(customer_no__startswith=DEMO_CUSTOMER_PREFIX).delete()[0]
    _record_deleted(summary, "customers", deleted)


def _base_customer_profiles() -> list[dict[str, Any]]:
    rows = [
        ("华东精工材料有限公司", "制造业", "供应链"),
        ("申浦电子器件有限公司", "制造业", "供应链"),
        ("松江机电总装有限公司", "制造业", "供应链"),
        ("沪江化工原料有限公司", "化工", "供应链"),
        ("浦东仪表技术有限公司", "高端设备", "供应链"),
        ("蓝海物流协同有限公司", "物流", "供应链"),
        ("长港能源设备有限公司", "能源", "供应链"),
        ("远川金属加工有限公司", "制造业", "供应链"),
        ("安澜工业服务有限公司", "服务业", "供应链"),
        ("申城包装科技有限公司", "制造业", "供应链"),
        ("嘉佑建材供应有限公司", "建材", "供应链"),
        ("华河工程配套有限公司", "工程服务", "供应链"),
        ("浦江软件股份有限公司", "信息技术", "代发工资"),
        ("云帆医疗科技有限公司", "医疗器械", "代发工资"),
        ("同耀信息系统有限公司", "信息技术", "代发工资"),
        ("海岳网络服务有限公司", "信息服务", "代发工资"),
        ("锦程生物科技有限公司", "生物医药", "代发工资"),
        ("联辰新能源有限公司", "新能源", "代发工资"),
        ("领航咨询服务有限公司", "咨询服务", "代发工资"),
        ("瀚宇文化传媒有限公司", "文创传媒", "代发工资"),
        ("宏信物业管理有限公司", "物业", "代发工资"),
        ("鼎盛食品加工有限公司", "食品", "代发工资"),
        ("青浦会务服务有限公司", "会展服务", "日常费用"),
        ("虹桥商务运营有限公司", "商务服务", "日常费用"),
        ("静安办公后勤有限公司", "后勤服务", "日常费用"),
        ("浦南保洁服务有限公司", "物业", "日常费用"),
        ("东方设备维保有限公司", "设备运维", "日常费用"),
        ("华远交通服务有限公司", "交通服务", "日常费用"),
        ("云港仓储运营有限公司", "仓储", "日常费用"),
        ("申松行政服务有限公司", "行政服务", "日常费用"),
    ]
    return [
        {"name": name, "industry": industry, "biz_tag": biz_tag}
        for name, industry, biz_tag in rows
    ]


def _seed_customers(*, scale: str, summary: dict[str, Any]) -> list[Customer]:
    target = SCALE_CONFIG[scale]["customers"]
    base = _base_customer_profiles()

    if target > len(base):
        for idx in range(len(base) + 1, target + 1):
            base.append(
                {
                    "name": f"示例企业{idx:02d}有限公司",
                    "industry": "综合服务",
                    "biz_tag": "日常费用",
                }
            )

    rows = base[:target]

    if target == 30:
        statuses = ["ACTIVE"] * 22 + ["PENDING"] * 5 + ["FROZEN"] * 3
        mobiles = (
            [None] * 20
            + [f"1391000{idx:04d}" for idx in range(1, 3)]
            + [None] * 3
            + [f"1392000{idx:04d}" for idx in range(1, 3)]
            + [None]
            + [f"1393000{idx:04d}" for idx in range(1, 3)]
        )
    else:
        status_counts = _scaled_counts(target, {"ACTIVE": 22, "PENDING": 5, "FROZEN": 3})
        statuses = (
            ["ACTIVE"] * status_counts["ACTIVE"]
            + ["PENDING"] * status_counts["PENDING"]
            + ["FROZEN"] * status_counts["FROZEN"]
        )
        null_count = int(round(target * (24 / 30)))
        mobiles = [None] * null_count + [f"138{idx:08d}" for idx in range(1, target - null_count + 1)]

    customers: list[Customer] = []
    now = timezone.now()
    for idx, row in enumerate(rows, start=1):
        status = statuses[idx - 1]
        mobile = mobiles[idx - 1] if idx - 1 < len(mobiles) else None
        grade = "A" if status == "ACTIVE" else ("B" if status == "PENDING" else "C")
        created_at_hint = now - timedelta(days=(46 - min(idx, 45)))
        customer = _upsert(
            model=Customer,
            lookup={"customer_no": f"{DEMO_CUSTOMER_PREFIX}{idx:04d}"},
            defaults={
                "name": row["name"],
                "mobile": mobile,
                "amount_total": Decimal("100000.00") + Decimal(idx * 3100),
                "status": status,
                "profile_json": {
                    "industry": row["industry"],
                    "region": "上海",
                    "customer_grade": grade,
                    "onboard_at": created_at_hint.strftime("%Y-%m-%d"),
                },
                "tags_json": [row["biz_tag"], "对公客户"],
            },
            summary=summary,
            summary_key="customers",
        )
        customers.append(customer)
    return customers


def _seed_accounts(
    *,
    scale: str,
    customers: list[Customer],
    summary: dict[str, Any],
) -> list[Account]:
    target = min(SCALE_CONFIG[scale]["accounts"], len(customers))
    if target <= 0:
        return []

    if target == 24:
        statuses = ["NORMAL"] * 20 + ["LOCKED"] * 2 + ["DORMANT"] * 2
    else:
        counts = _scaled_counts(target, {"NORMAL": 20, "LOCKED": 2, "DORMANT": 2})
        statuses = (
            ["NORMAL"] * counts["NORMAL"]
            + ["LOCKED"] * counts["LOCKED"]
            + ["DORMANT"] * counts["DORMANT"]
        )

    accounts: list[Account] = []
    now = timezone.now()
    for idx in range(1, target + 1):
        customer = customers[idx - 1]
        status = statuses[idx - 1]
        account = _upsert(
            model=Account,
            lookup={"account_no": f"{DEMO_ACCOUNT_PREFIX}{idx:04d}"},
            defaults={
                "customer": customer,
                "balance_amount": Decimal("180000.00") + Decimal(idx * 5200),
                "opened_at": now - timedelta(days=120 + idx),
                "status": status,
                "ledger_json": {
                    "currency": "CNY",
                    "ledger_no": f"LEDGER-{idx:04d}",
                    "book": "CN-CORP",
                },
                "ext_json": {
                    "branch": "上海分行营业部",
                    "channel": "企业网银",
                },
            },
            summary=summary,
            summary_key="accounts",
        )
        accounts.append(account)
    return accounts


def _seed_txns(
    *,
    scale: str,
    customers: list[Customer],
    accounts: list[Account],
    users: dict[str, User],
    summary: dict[str, Any],
) -> list[Txn]:
    target = SCALE_CONFIG[scale]["txns"]
    medium_specs = _build_medium_txn_specs(customers=customers, accounts=accounts)
    specs = medium_specs[:target]
    if target > len(specs):
        specs.extend(_build_extra_txn_specs(target - len(specs), customers, accounts))

    now = timezone.now()
    txns: list[Txn] = []
    maker_users = [users["maker_01"], users["maker_02"]]
    phase_with_maker = {
        TxnCorePhase.REVIEW_PENDING,
        TxnCorePhase.APPROVED,
        TxnCorePhase.BOOKED,
        TxnCorePhase.CLEARED,
        TxnCorePhase.ACKED,
        TxnCorePhase.REJECTED,
    }
    phase_with_checker = {
        TxnCorePhase.APPROVED,
        TxnCorePhase.BOOKED,
        TxnCorePhase.CLEARED,
        TxnCorePhase.ACKED,
        TxnCorePhase.REJECTED,
    }

    for idx, spec in enumerate(specs, start=1):
        phase = spec["phase"]
        txn_at = now - timedelta(days=spec["days_ago"], hours=spec["hour"], minutes=spec["minute"])
        maker = maker_users[idx % 2] if phase in phase_with_maker else None
        checker = users["checker_01"] if phase in phase_with_checker else None
        payload = {
            "scenario": spec["scenario"],
            "business_type": "CORP_TRANSFER",
            "purpose": spec["purpose"],
            "batch_no": spec["batch_no"],
            "channel": "企业网银",
            "same_bank": spec["same_bank"],
        }
        tags = ["priority" if spec["amount"] >= Decimal("300000") else "normal"]
        if not spec["same_bank"]:
            tags.append("cross_bank")
        if spec["scenario"] == "payroll_batch":
            tags.append("batch_payroll")

        txn = _upsert(
            model=Txn,
            lookup={"txn_no": spec["txn_no"]},
            defaults={
                "customer": spec["customer"],
                "account": spec["account"],
                "amount": spec["amount"],
                "txn_at": txn_at,
                "status": phase,
                "core_phase": phase,
                "maker_user": maker,
                "checker_user": checker,
                "phase_updated_at": txn_at + timedelta(minutes=40),
                "payload_json": payload,
                "tags_json": tags,
            },
            summary=summary,
            summary_key="txns",
        )
        txns.append(txn)
    return txns


def _build_medium_txn_specs(
    *,
    customers: list[Customer],
    accounts: list[Account],
) -> list[dict[str, Any]]:
    if len(customers) < 24 or len(accounts) < 24:
        raise ValueError("Need at least 24 customers/accounts before seeding medium txns.")

    def ca(c_idx: int, a_idx: int) -> tuple[Customer, Account]:
        return customers[c_idx - 1], accounts[a_idx - 1]

    specs: list[dict[str, Any]] = []
    phases_a = [
        TxnCorePhase.RECEIVED,
        TxnCorePhase.REVIEW_PENDING,
        TxnCorePhase.APPROVED,
        TxnCorePhase.BOOKED,
        TxnCorePhase.CLEARED,
        TxnCorePhase.ACKED,
        TxnCorePhase.RECEIVED,
        TxnCorePhase.APPROVED,
        TxnCorePhase.BOOKED,
        TxnCorePhase.CLEARED,
        TxnCorePhase.RECEIVED,
        TxnCorePhase.APPROVED,
    ]
    amounts_a = [
        Decimal("320000.00"),
        Decimal("280000.00"),
        Decimal("450000.00"),
        Decimal("210000.00"),
        Decimal("180000.00"),
        Decimal("160000.00"),
        Decimal("390000.00"),
        Decimal("260000.00"),
        Decimal("230000.00"),
        Decimal("175000.00"),
        Decimal("500000.00"),
        Decimal("340000.00"),
    ]
    for idx, phase in enumerate(phases_a, start=1):
        customer, account = ca(idx, idx)
        txn_no = "TXN-DEMO-CHAIN-0001" if idx == 1 else f"{DEMO_TXN_PREFIX}{idx:04d}"
        specs.append(
            {
                "txn_no": txn_no,
                "phase": phase,
                "customer": customer,
                "account": account,
                "scenario": "supplier_payment",
                "purpose": f"供应商货款结算-{idx:02d}",
                "batch_no": f"SUP-202602-{idx:02d}",
                "same_bank": idx % 2 == 0,
                "amount": amounts_a[idx - 1],
                "days_ago": 44 - idx,
                "hour": 9 + (idx % 5),
                "minute": 5 + idx,
            }
        )

    phases_b = [
        TxnCorePhase.RECEIVED,
        TxnCorePhase.REVIEW_PENDING,
        TxnCorePhase.APPROVED,
        TxnCorePhase.ACKED,
        TxnCorePhase.BOOKED,
        TxnCorePhase.CLEARED,
        TxnCorePhase.ACKED,
        TxnCorePhase.APPROVED,
        TxnCorePhase.BOOKED,
        TxnCorePhase.RECEIVED,
    ]
    amounts_b = [
        Decimal("68000.00"),
        Decimal("72000.00"),
        Decimal("55000.00"),
        Decimal("30000.00"),
        Decimal("45000.00"),
        Decimal("62000.00"),
        Decimal("58000.00"),
        Decimal("61000.00"),
        Decimal("47000.00"),
        Decimal("52000.00"),
    ]
    for offset, phase in enumerate(phases_b, start=1):
        index = len(specs) + 1
        c_idx = 12 + offset
        customer, account = ca(c_idx, c_idx)
        specs.append(
            {
                "txn_no": f"{DEMO_TXN_PREFIX}{index:04d}",
                "phase": phase,
                "customer": customer,
                "account": account,
                "scenario": "payroll_batch",
                "purpose": f"工资代发批次-PAY-20260301-A-{offset:02d}",
                "batch_no": "PAY-20260301-A",
                "same_bank": True,
                "amount": amounts_b[offset - 1],
                "days_ago": 12,
                "hour": 10,
                "minute": 10 + offset,
            }
        )

    phases_c = [
        TxnCorePhase.APPROVED,
        TxnCorePhase.CLEARED,
        TxnCorePhase.ACKED,
        TxnCorePhase.RECEIVED,
        TxnCorePhase.APPROVED,
        TxnCorePhase.BOOKED,
        TxnCorePhase.CLEARED,
        TxnCorePhase.ACKED,
    ]
    amounts_c = [
        Decimal("1200.00"),
        Decimal("900.00"),
        Decimal("1500.00"),
        Decimal("800.00"),
        Decimal("2000.00"),
        Decimal("1100.00"),
        Decimal("1800.00"),
        Decimal("950.00"),
    ]
    for offset, phase in enumerate(phases_c, start=1):
        index = len(specs) + 1
        c_idx = 16 + offset
        customer, account = ca(c_idx, c_idx)
        specs.append(
            {
                "txn_no": f"{DEMO_TXN_PREFIX}{index:04d}",
                "phase": phase,
                "customer": customer,
                "account": account,
                "scenario": "daily_settlement",
                "purpose": f"日常费用结算-{offset:02d}",
                "batch_no": f"OPS-202603-{offset:02d}",
                "same_bank": offset % 2 == 1,
                "amount": amounts_c[offset - 1],
                "days_ago": 7 - offset,
                "hour": 14 + (offset % 3),
                "minute": 12 + offset,
            }
        )

    phases_d = [
        TxnCorePhase.REVIEW_PENDING,
        TxnCorePhase.REVIEW_PENDING,
        TxnCorePhase.REVIEW_PENDING,
        TxnCorePhase.REJECTED,
    ]
    amounts_d = [
        Decimal("15000.00"),
        Decimal("22000.00"),
        Decimal("28000.00"),
        Decimal("26000.00"),
    ]
    pairs_d = [(3, 3), (14, 14), (21, 21), (22, 22)]
    reasons = [
        "受益人信息待补充",
        "付款用途描述不完整",
        "付款指令附件待补录",
        "账户状态不符，复核拒绝",
    ]
    for offset, phase in enumerate(phases_d, start=1):
        index = len(specs) + 1
        c_idx, a_idx = pairs_d[offset - 1]
        customer, account = ca(c_idx, a_idx)
        txn_no = "TXN-DEMO-REJECT-0001" if phase == TxnCorePhase.REJECTED else f"{DEMO_TXN_PREFIX}{index:04d}"
        specs.append(
            {
                "txn_no": txn_no,
                "phase": phase,
                "customer": customer,
                "account": account,
                "scenario": "review_reject_case",
                "purpose": reasons[offset - 1],
                "batch_no": f"EXC-202603-{offset:02d}",
                "same_bank": False,
                "amount": amounts_d[offset - 1],
                "days_ago": 4 - offset,
                "hour": 16,
                "minute": 20 + offset,
            }
        )

    return specs


def _build_extra_txn_specs(
    extra_count: int,
    customers: list[Customer],
    accounts: list[Account],
) -> list[dict[str, Any]]:
    phases = [
        TxnCorePhase.RECEIVED,
        TxnCorePhase.REVIEW_PENDING,
        TxnCorePhase.APPROVED,
        TxnCorePhase.BOOKED,
        TxnCorePhase.CLEARED,
        TxnCorePhase.ACKED,
    ]
    rows: list[dict[str, Any]] = []
    for idx in range(1, extra_count + 1):
        customer = customers[(idx - 1) % len(customers)]
        account = accounts[(idx - 1) % len(accounts)]
        rows.append(
            {
                "txn_no": f"{DEMO_TXN_PREFIX}EX{idx:03d}",
                "phase": phases[idx % len(phases)],
                "customer": customer,
                "account": account,
                "scenario": "daily_settlement",
                "purpose": f"扩展样本交易-{idx:03d}",
                "batch_no": f"EXT-202603-{idx:03d}",
                "same_bank": idx % 2 == 0,
                "amount": Decimal("1000.00") + Decimal(idx * 220),
                "days_ago": 5 + idx,
                "hour": 11,
                "minute": idx % 60,
            }
        )
    return rows


def _seed_risk_cases(
    *,
    scale: str,
    customers: list[Customer],
    accounts: list[Account],
    txns: list[Txn],
    users: dict[str, User],
    summary: dict[str, Any],
) -> list[RiskCase]:
    target = SCALE_CONFIG[scale]["risk_cases"]

    phase_counts = (
        {"OPEN": 8, "REVIEWING": 6, "BLOCKED": 4, "RELEASED": 3, "CLOSED": 5}
        if target == 26
        else _scaled_counts(
            target,
            {"OPEN": 8, "REVIEWING": 6, "BLOCKED": 4, "RELEASED": 3, "CLOSED": 5},
        )
    )
    phases = _expand_statuses(
        phase_counts,
        ["OPEN", "REVIEWING", "BLOCKED", "RELEASED", "CLOSED"],
    )

    manual_close_true_target = 6 if target == 26 else max(1, round(target * (6 / 26)))
    manual_close_true_set = set(range(1, manual_close_true_target + 1))

    now = timezone.now()
    rows: list[RiskCase] = []
    for idx in range(1, target + 1):
        phase = phases[idx - 1]
        ref_txn = txns[(idx - 1) % len(txns)]
        case_no = f"{DEMO_RISK_PREFIX}{idx:04d}"
        if idx == 1:
            case_no = "RISK-DEMO-CHAIN-0001"
        elif idx == 2:
            case_no = "RISK-DEMO-REJECT-0001"

        if phase == RiskPhase.OPEN:
            linked_txn_no = None
            reviewed_by = None
            reviewed_at = None
        else:
            linked_txn_no = ref_txn.txn_no
            reviewed_by = users["checker_01"]
            reviewed_at = now - timedelta(days=max(0, 30 - idx), hours=2)

        manual_close = idx in manual_close_true_set
        risk = _upsert(
            model=RiskCase,
            lookup={"case_no": case_no},
            defaults={
                "customer": ref_txn.customer,
                "account": ref_txn.account,
                "risk_amount": max(Decimal("500.00"), ref_txn.amount * Decimal("0.85")),
                "detected_at": now - timedelta(days=max(1, 34 - idx), hours=idx % 6),
                "status": phase,
                "risk_phase": phase,
                "linked_txn_no": linked_txn_no,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "rules_json": {
                    "manual_close": manual_close,
                    "rule_pack": "CORP_TRANSFER_BASE",
                    "rule_tag": "交易行为监测",
                },
                "evidence_json": {
                    "risk_score": 55 + (idx % 40),
                    "source": "规则引擎",
                    "channel": "企业网银",
                },
            },
            summary=summary,
            summary_key="risk_cases",
        )
        rows.append(risk)
    return rows


def _seed_cdrs(
    *,
    scale: str,
    customers: list[Customer],
    accounts: list[Account],
    summary: dict[str, Any],
) -> list[Cdr]:
    target = SCALE_CONFIG[scale]["cdrs"]
    if target <= 0:
        return []

    if target == 24:
        status_counts = {"SUCCESS": 14, "FAILED": 5, "PENDING": 5}
    else:
        status_counts = _scaled_counts(target, {"SUCCESS": 14, "FAILED": 5, "PENDING": 5})
    statuses = _expand_statuses(status_counts, ["SUCCESS", "FAILED", "PENDING"])

    now = timezone.now()
    rows: list[Cdr] = []
    for idx in range(1, target + 1):
        account = accounts[(idx - 1) % len(accounts)]
        customer = account.customer
        status = statuses[idx - 1]
        cdr = _upsert(
            model=Cdr,
            lookup={"cdr_no": f"{DEMO_CDR_PREFIX}{idx:04d}"},
            defaults={
                "customer": customer,
                "account": account,
                "charge_amount": Decimal("1.20") + Decimal(idx) / Decimal("10"),
                "cdr_at": now - timedelta(days=idx % 28, hours=idx % 8),
                "status": status,
                "route_json": {
                    "route": "CNAPS",
                    "node": f"SH-{100 + idx:03d}",
                },
                "extra_json": {
                    "notify": status == "SUCCESS",
                    "channel": "短信",
                },
            },
            summary=summary,
            summary_key="cdrs",
        )
        rows.append(cdr)
    return rows


def _seed_bills(
    *,
    scale: str,
    accounts: list[Account],
    summary: dict[str, Any],
) -> list[BillMonthly]:
    target = SCALE_CONFIG[scale]["bills"]
    if target <= 0:
        return []

    if target == 24:
        status_counts = {"PAID": 12, "GENERATED": 8, "OVERDUE": 4}
    else:
        status_counts = _scaled_counts(target, {"PAID": 12, "GENERATED": 8, "OVERDUE": 4})
    statuses = _expand_statuses(status_counts, ["PAID", "GENERATED", "OVERDUE"])

    months = ["2026-01", "2026-02"]
    now = timezone.now()
    rows: list[BillMonthly] = []
    idx = 0
    while len(rows) < target:
        account = accounts[idx % len(accounts)]
        month = months[(idx // len(accounts)) % len(months)]
        status = statuses[len(rows)]
        bill = _upsert(
            model=BillMonthly,
            lookup={
                "customer": account.customer,
                "account": account,
                "bill_month": month,
            },
            defaults={
                "bill_amount": Decimal("2200.00") + Decimal((idx % 12) * 360),
                "generated_at": now - timedelta(days=35 if month == "2026-01" else 5, hours=idx % 7),
                "status": status,
                "summary_json": {
                    "item_count": 6 + (idx % 5),
                    "tax_included": True,
                },
                "detail_json": {
                    "service_fee": 120 + (idx % 10),
                    "transfer_fee": 80 + (idx % 8),
                },
            },
            summary=summary,
            summary_key="bills",
        )
        rows.append(bill)
        idx += 1
    return rows


def _scaled_counts(total: int, base: dict[str, int]) -> dict[str, int]:
    base_total = sum(base.values())
    raw = {k: (total * v / base_total) for k, v in base.items()}
    floor_map = {k: int(raw[k]) for k in base}
    remainder = total - sum(floor_map.values())

    if remainder > 0:
        order = sorted(base.keys(), key=lambda k: (raw[k] - floor_map[k]), reverse=True)
        for idx in range(remainder):
            floor_map[order[idx % len(order)]] += 1
    return floor_map


def _expand_statuses(counts: dict[str, int], order: list[str]) -> list[str]:
    rows: list[str] = []
    for key in order:
        rows.extend([key] * counts.get(key, 0))
    return rows
