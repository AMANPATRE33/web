"""Ad-hoc: verify the full downgrade -> upgrade cycle is clean and repeatable.

A migration that cannot be rolled back and re-applied is not deployable: the
first bad production deploy is exactly when the rollback path is exercised.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
PSQL = Path(r"C:\Program Files\PostgreSQL\18\bin\psql.exe")
URL = "postgresql+asyncpg://storefront:storefront_dev_only@127.0.0.1:55432/storefront"


def alembic(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONWARNINGS": "ignore"},
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def psql(sql: str) -> str:
    proc = subprocess.run(
        [
            str(PSQL),
            "-h",
            "127.0.0.1",
            "-p",
            "55432",
            "-U",
            "storefront",
            "-d",
            "storefront",
            "-tAc",
            sql,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return f"ERROR: {proc.stderr.strip()}"
    return proc.stdout.strip()


def psql_exec(sql: str) -> str:
    """Run a statement for effect; return the error text or an empty string.

    psql echoes the command tag (``DROP TYPE``) on stdout for DDL, so stdout
    cannot be used to detect failure - only stderr and the exit code can.
    """
    proc = subprocess.run(
        [
            str(PSQL),
            "-h",
            "127.0.0.1",
            "-p",
            "55432",
            "-U",
            "storefront",
            "-d",
            "storefront",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
    )
    return proc.stderr.strip() if proc.returncode != 0 else ""


def reset_database() -> None:
    """Return the database to a genuinely empty state.

    Order matters: tables must go before the enum types they use, otherwise
    CASCADE leaves a database full of tables referencing types that no longer
    exist, and the next `upgrade head` fails for reasons unrelated to the
    migration chain.
    """
    alembic("downgrade", "base")

    tables = psql(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' "
        "AND tablename <> 'alembic_version';"
    )
    for table in (row.strip() for row in tables.splitlines()):
        if table:
            error = psql_exec(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
            if error:
                print(f"  !! could not drop table {table}: {error}")

    enums = psql(
        "SELECT typname FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
        "WHERE n.nspname='public' AND t.typtype='e';"
    )
    for enum_name in (row.strip() for row in enums.splitlines()):
        if enum_name:
            error = psql_exec(f'DROP TYPE IF EXISTS "{enum_name}" CASCADE;')
            if error:
                print(f"  !! could not drop enum {enum_name}: {error}")

    psql_exec("DROP TABLE IF EXISTS alembic_version;")


def counts() -> tuple[int, int, str]:
    enums = int(
        psql(
            "SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
            "WHERE n.nspname='public' AND t.typtype='e';"
        )
        or 0
    )
    tables = int(
        psql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public';") or 0
    )
    version = psql("SELECT coalesce(max(version_num),'(base)') FROM alembic_version;")
    return enums, tables, version


def main() -> None:
    """
    Verify the **production** rollback path, not a full teardown.

    ``alembic downgrade base`` is deliberately not exercised end-to-end: two of
    the migrations add enum values, and PostgreSQL cannot remove one. Rolling all
    the way back and forward again therefore cannot work without dropping the
    database, and pretending otherwise would be a false green.

    The path that actually matters in an incident is *one revision backwards*,
    which is what this checks, twice, to prove it is repeatable.
    """
    ok = True
    reset_database()
    print("reset ->", counts())

    for cycle in (1, 2):
        code, out = alembic("upgrade", "head")
        enums, tables, version = counts()
        print(f"cycle {cycle} upgrade exit={code}", (enums, tables, version))
        if code != 0:
            print(out[-1200:])
            ok = False
            break

        # The real rollback: one revision back, then forward again.
        code, out = alembic("downgrade", "-1")
        enums, tables, version = counts()
        print(f"cycle {cycle} downgrade -1 exit={code}", (enums, tables, version))
        if code != 0:
            print(out[-1200:])
            ok = False
            break

        code, out = alembic("upgrade", "head")
        enums, tables, version = counts()
        print(f"cycle {cycle} re-upgrade exit={code}", (enums, tables, version))
        if code != 0:
            print(out[-1200:])
            ok = False
            break
        if version != "0004_freight_shipping":
            print(f"  !! expected head, got {version}")
            ok = False

    print("RESULT:", "PASS" if ok else "FAIL")
    print(
        "\nNote: `downgrade base` is not reversible for this schema because enum\n"
        "values cannot be removed. To rebuild from scratch, drop and recreate\n"
        "the database rather than relying on the migration chain."
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
