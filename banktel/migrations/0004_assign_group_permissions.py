from django.db import migrations


MAKER_GROUP = "txn_maker"
CHECKER_GROUP = "txn_checker"


def assign_group_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    maker, _ = Group.objects.get_or_create(name=MAKER_GROUP)
    checker, _ = Group.objects.get_or_create(name=CHECKER_GROUP)

    txn_ct = ContentType.objects.filter(app_label="banktel", model="txn").first()
    risk_ct = ContentType.objects.filter(app_label="banktel", model="riskcase").first()
    if not txn_ct or not risk_ct:
        return

    maker_perms = Permission.objects.filter(
        content_type=txn_ct,
        codename__in=["view_txn", "change_txn"],
    )

    checker_perms = Permission.objects.filter(
        content_type__in=[txn_ct, risk_ct],
        codename__in=["view_txn", "change_txn", "view_riskcase", "change_riskcase"],
    )

    maker.permissions.add(*maker_perms)
    checker.permissions.add(*checker_perms)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("banktel", "0003_seed_flow_fields_and_groups"),
    ]

    operations = [
        migrations.RunPython(assign_group_permissions, noop_reverse),
    ]
