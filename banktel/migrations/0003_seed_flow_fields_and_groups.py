from django.db import migrations


TXN_STATUS_TO_PHASE = {
    "RECEIVED": "RECEIVED",
    "REVIEW_PENDING": "REVIEW_PENDING",
    "APPROVED": "APPROVED",
    "REJECTED": "REJECTED",
    "BOOKED": "BOOKED",
    "CLEARED": "CLEARED",
    "ACKED": "ACKED",
}

RISK_STATUS_TO_PHASE = {
    "OPEN": "OPEN",
    "REVIEWING": "REVIEWING",
    "BLOCKED": "BLOCKED",
    "RELEASED": "RELEASED",
    "CLOSED": "CLOSED",
}


def seed_flow_fields(apps, schema_editor):
    Txn = apps.get_model("banktel", "Txn")
    RiskCase = apps.get_model("banktel", "RiskCase")
    Group = apps.get_model("auth", "Group")

    Group.objects.get_or_create(name="txn_maker")
    Group.objects.get_or_create(name="txn_checker")

    for txn in Txn.objects.all().iterator():
        phase = TXN_STATUS_TO_PHASE.get((txn.status or "").upper(), "RECEIVED")
        updates = []
        if txn.core_phase != phase:
            txn.core_phase = phase
            updates.append("core_phase")
        if txn.phase_updated_at is None:
            txn.phase_updated_at = txn.txn_at
            updates.append("phase_updated_at")
        if updates:
            txn.save(update_fields=updates)

    for risk_case in RiskCase.objects.all().iterator():
        phase = RISK_STATUS_TO_PHASE.get((risk_case.status or "").upper(), "OPEN")
        updates = []
        if risk_case.risk_phase != phase:
            risk_case.risk_phase = phase
            updates.append("risk_phase")
        if phase != "OPEN" and risk_case.reviewed_at is None:
            risk_case.reviewed_at = risk_case.detected_at
            updates.append("reviewed_at")
        if updates:
            risk_case.save(update_fields=updates)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("banktel", "0002_auto_20260305_1104"),
    ]

    operations = [
        migrations.RunPython(seed_flow_fields, noop_reverse),
    ]
