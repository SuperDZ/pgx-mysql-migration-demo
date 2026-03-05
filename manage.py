#!/usr/bin/env python
import os
import sys


def main() -> None:
    from demo_project.db_bootstrap import ensure_database_ready, should_bootstrap

    if should_bootstrap(sys.argv):
        ensure_database_ready()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo_project.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Install dependencies from requirements.txt first."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
