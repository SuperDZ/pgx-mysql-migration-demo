from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def ensure_flow_groups_permissions(sender, **kwargs):
    if sender.name != "banktel":
        return

    maker, _ = Group.objects.get_or_create(name="txn_maker")
    checker, _ = Group.objects.get_or_create(name="txn_checker")

    maker_perms = Permission.objects.filter(
        content_type__app_label="banktel",
        codename__in=["view_txn", "change_txn"],
    )
    checker_perms = Permission.objects.filter(
        content_type__app_label="banktel",
        codename__in=["view_txn", "change_txn", "view_riskcase", "change_riskcase"],
    )

    maker.permissions.add(*maker_perms)
    checker.permissions.add(*checker_perms)
