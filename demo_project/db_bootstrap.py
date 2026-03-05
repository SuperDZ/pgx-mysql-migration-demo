from __future__ import annotations

import logging
import os
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

import psycopg2
from psycopg2 import sql
import pymysql
from dotenv import load_dotenv

LOGGER = logging.getLogger("bootstrap")


BOOTSTRAP_COMMANDS = {
    "runserver",
    "migrate",
    "makemigrations",
    "check",
    "createsuperuser",
    "shell",
}


def should_bootstrap(argv: list[str]) -> bool:
    if len(argv) < 2:
        return False
    command = argv[1].strip().lower()
    if command not in BOOTSTRAP_COMMANDS:
        return False
    if command == "runserver" and os.environ.get("RUN_MAIN") == "true":
        return False
    return True


def _ensure_bootstrap_logger(base_dir: Path) -> None:
    if LOGGER.handlers:
        return

    log_dir = base_dir / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    file_handler = TimedRotatingFileHandler(
        log_dir / "bootstrap.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(stream_handler)


def ensure_database_ready() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    _ensure_bootstrap_logger(base_dir)
    load_dotenv(base_dir / ".env")

    db_target = os.getenv("DB_TARGET", "mysql").strip().lower()
    LOGGER.info("target=%s", db_target)

    if db_target == "mysql":
        _ensure_mysql_database()
    elif db_target in {"pgx", "pg"}:
        _ensure_postgresql_database(db_target)
    else:
        raise ValueError("DB_TARGET must be one of: mysql, pgx, pg")


def _ensure_mysql_database() -> None:
    host = os.getenv("MYSQL_HOST", "192.168.31.15")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    db_name = os.getenv("MYSQL_DB", "demo")
    grant_host = os.getenv("MYSQL_GRANT_HOST", "%")

    LOGGER.info("[mysql] checking database '%s' on %s:%s", db_name, host, port)

    with pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database="mysql",
        charset="utf8mb4",
        autocommit=True,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s",
                (db_name,),
            )
            exists = cursor.fetchone() is not None

            if exists:
                LOGGER.info("[mysql] database '%s' already exists", db_name)
            else:
                safe_db_name = db_name.replace("`", "``")
                cursor.execute(
                    f"CREATE DATABASE `{safe_db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                LOGGER.info("[mysql] database '%s' created", db_name)

            safe_db_name = db_name.replace("`", "``")
            try:
                cursor.execute(
                    f"GRANT ALL PRIVILEGES ON `{safe_db_name}`.* TO %s@%s",
                    (user, grant_host),
                )
                cursor.execute("FLUSH PRIVILEGES")
                LOGGER.info(
                    "[mysql] granted privileges on '%s' to '%s'@'%s'",
                    db_name,
                    user,
                    grant_host,
                )
            except pymysql.MySQLError as exc:
                LOGGER.warning(
                    "[mysql] grant skipped due to permission error: %s",
                    exc,
                )


def _ensure_postgresql_database(db_target: str) -> None:
    if db_target == "pgx":
        host = os.getenv("PGX_HOST", "192.168.31.10")
        port = int(os.getenv("PGX_PORT", "5432"))
        user = os.getenv("PGX_USER", "postgresql")
        password = os.getenv("PGX_PASSWORD", "")
        db_name = os.getenv("PGX_DB", "demo")
    else:
        host = os.getenv("PG_HOST", "192.168.31.20")
        port = int(os.getenv("PG_PORT", "5432"))
        user = os.getenv("PG_USER", "postgresql")
        password = os.getenv("PG_PASSWORD", "")
        db_name = os.getenv("PG_DB", "demo")

    LOGGER.info(
        "[%s] checking database '%s' on %s:%s",
        db_target,
        db_name,
        host,
        port,
    )

    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname="postgres",
    )
    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            exists = cursor.fetchone() is not None

            if exists:
                LOGGER.info("[%s] database '%s' already exists", db_target, db_name)
            else:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name))
                )
                LOGGER.info("[%s] database '%s' created", db_target, db_name)

            try:
                cursor.execute(
                    sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                        sql.Identifier(db_name), sql.Identifier(user)
                    )
                )
                LOGGER.info(
                    "[%s] granted privileges on '%s' to '%s'",
                    db_target,
                    db_name,
                    user,
                )
            except psycopg2.Error as exc:
                LOGGER.warning(
                    "[%s] grant skipped due to permission error: %s",
                    db_target,
                    exc,
                )
    finally:
        conn.close()
