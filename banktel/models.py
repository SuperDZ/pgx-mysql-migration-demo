from django.db import models


class TxnCorePhase(models.TextChoices):
    RECEIVED = "RECEIVED", "受理"
    REVIEW_PENDING = "REVIEW_PENDING", "待复核"
    APPROVED = "APPROVED", "复核通过"
    REJECTED = "REJECTED", "复核拒绝"
    BOOKED = "BOOKED", "记账完成"
    CLEARED = "CLEARED", "清算完成"
    ACKED = "ACKED", "回执完成"


class RiskPhase(models.TextChoices):
    OPEN = "OPEN", "已打开"
    REVIEWING = "REVIEWING", "审核中"
    BLOCKED = "BLOCKED", "已拦截"
    RELEASED = "RELEASED", "已放行"
    CLOSED = "CLOSED", "已闭环"


class Customer(models.Model):
    customer_no = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=64)
    mobile = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    amount_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=20, db_index=True)
    profile_json = models.JSONField(default=dict)
    tags_json = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"{self.customer_no} - {self.name}"


class Account(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="accounts"
    )
    account_no = models.CharField(max_length=32, unique=True, db_index=True)
    balance_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    opened_at = models.DateTimeField()
    status = models.CharField(max_length=20, db_index=True)
    ledger_json = models.JSONField(default=dict)
    ext_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.account_no


class Txn(models.Model):
    txn_no = models.CharField(max_length=40, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="txns")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="txns")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    txn_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, db_index=True)
    core_phase = models.CharField(
        max_length=20,
        choices=TxnCorePhase.choices,
        default=TxnCorePhase.RECEIVED,
        db_index=True,
    )
    maker_user = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="txn_maker_records",
    )
    checker_user = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="txn_checker_records",
    )
    phase_updated_at = models.DateTimeField(null=True, blank=True, db_index=True)
    payload_json = models.JSONField(default=dict)
    tags_json = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-txn_at", "-id"]

    def __str__(self) -> str:
        return self.txn_no


class Cdr(models.Model):
    cdr_no = models.CharField(max_length=40, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="cdrs")
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="cdrs"
    )
    charge_amount = models.DecimalField(max_digits=18, decimal_places=2)
    cdr_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, db_index=True)
    route_json = models.JSONField(default=dict)
    extra_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cdr_at", "-id"]

    def __str__(self) -> str:
        return self.cdr_no


class BillMonthly(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="bills")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="bills")
    bill_month = models.CharField(max_length=7, db_index=True)
    bill_amount = models.DecimalField(max_digits=18, decimal_places=2)
    generated_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, db_index=True)
    summary_json = models.JSONField(default=dict)
    detail_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at", "-id"]

    def __str__(self) -> str:
        return f"{self.bill_month} - {self.id}"


class RiskCase(models.Model):
    case_no = models.CharField(max_length=40, unique=True, db_index=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="risk_cases"
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_cases",
    )
    risk_amount = models.DecimalField(max_digits=18, decimal_places=2)
    detected_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, db_index=True)
    risk_phase = models.CharField(
        max_length=20,
        choices=RiskPhase.choices,
        default=RiskPhase.OPEN,
        db_index=True,
    )
    linked_txn_no = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    reviewed_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="risk_review_records",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    rules_json = models.JSONField(default=dict)
    evidence_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-detected_at", "-id"]

    def __str__(self) -> str:
        return self.case_no
