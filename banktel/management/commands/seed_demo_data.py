from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from banktel.services.seed_data import seed_demo_data


class Command(BaseCommand):
    help = "导入论文演示用仿真数据（支持幂等、支持 reset）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scale",
            choices=["small", "medium", "large"],
            default="medium",
            help="数据规模，默认 medium。",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="导入前先清理已有 DEMO 前缀数据。",
        )
        parser.add_argument(
            "--password",
            default="Demo@123456",
            help="演示账号密码，默认 Demo@123456。",
        )

    def handle(self, *args, **options):
        scale = options["scale"]
        reset = bool(options["reset"])
        password = options["password"]

        try:
            summary = seed_demo_data(scale=scale, reset=reset, password=password)
        except Exception as exc:
            raise CommandError(f"seed_demo_data 执行失败: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"仿真数据导入完成，scale={summary['scale']}"))
        self.stdout.write("-" * 66)
        self._print_item("groups", summary)
        self._print_item("users", summary)
        self._print_item("customers", summary)
        self._print_item("accounts", summary)
        self._print_item("txns", summary)
        self._print_item("risk_cases", summary)
        self._print_item("cdrs", summary)
        self._print_item("bills", summary)

        if summary.get("deleted"):
            self.stdout.write("-" * 66)
            self.stdout.write("reset 删除统计：")
            for key, value in summary["deleted"].items():
                self.stdout.write(f"  {key:10s} deleted={value}")

        self.stdout.write("-" * 66)
        self.stdout.write("演示账号：")
        self.stdout.write("  demo_admin / demo_maker_01 / demo_maker_02 / demo_checker_01 / demo_viewer_01")
        self.stdout.write(f"  密码：{password}")

    def _print_item(self, key: str, summary):
        item = summary.get(key, {})
        created = item.get("created", 0)
        updated = item.get("updated", 0)
        self.stdout.write(f"{key:10s} created={created:3d} updated={updated:3d}")
