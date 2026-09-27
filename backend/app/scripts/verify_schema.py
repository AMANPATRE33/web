"""Fail loudly when the live database no longer matches the SQLAlchemy models.

Run this after ``alembic upgrade head`` and as a Railway pre-deploy step. A
schema that has drifted from the models produces errors that look like
application bugs, so it is worth detecting explicitly.

Exit codes: ``0`` in sync, ``1`` drift detected, ``2`` database unreachable.
"""

from __future__ import annotations

import asyncio
import sys

import app.models  # noqa: F401  (populates Base.metadata)
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine
from sqlalchemy import Connection, text

#: Differences that are noise rather than drift.
_IGNORED_SCHEMAS = {"pg_catalog", "information_schema"}


def _describe(diffs: list[dict[str, object]]) -> list[str]:
    """Render Alembic's diff structures as readable lines.

    Alembic represents most differences as dicts, but ``modify_type`` and
    ``modify_nullable`` arrive as positional lists. Both shapes are handled so
    the report never crashes on the difference it was written to surface.
    """
    lines: list[str] = []
    for diff in diffs:
        if isinstance(diff, dict):
            kind = diff.get("type")
            table = diff.get("table_name")
            column = (
                (diff.get("column") or {}).get("name")
                if isinstance(diff.get("column"), dict)
                else None
            )
            name = diff.get("index_name") or diff.get("constraint_name")
        elif isinstance(diff, list | tuple) and diff:
            kind = diff[0]
            table = diff[2] if len(diff) > 2 else None
            column = diff[3] if len(diff) > 3 else None
            name = None
        else:  # pragma: no cover - defensive
            lines.append(f"  unrecognised diff: {diff!r}")
            continue

        target = f"{table}.{column}" if table and column else (name or table or "?")

        match kind:
            case "add_table":
                lines.append(f"  table missing in database: {table}")
            case "remove_table":
                lines.append(f"  table not in models:       {table}")
            case "add_column":
                lines.append(f"  column missing:            {target}")
            case "remove_column":
                lines.append(f"  column not in models:      {target}")
            case "add_index":
                lines.append(f"  index missing:             {name}")
            case "remove_index":
                lines.append(f"  index not in models:       {name}")
            case "add_constraint":
                lines.append(f"  constraint missing:        {name}")
            case "remove_constraint":
                lines.append(f"  constraint not in models:  {name}")
            case "modify_type":
                lines.append(
                    f"  type changed:              {target} ({diff[-2]} -> {diff[-1]})"
                    if isinstance(diff, list | tuple)
                    else f"  type changed:              {target}"
                )
            case "modify_nullable":
                lines.append(f"  nullability changed:       {target}")
            case "modify_server_default":
                lines.append(f"  server default changed:    {target}")
            case _:
                lines.append(f"  {kind}: {target}")
    return lines


async def check() -> int:
    settings = get_settings()
    engine = get_engine(settings)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"Cannot connect to the database: {exc}")
        return 2

    def _compare(sync_connection: Connection) -> list[dict[str, object]]:
        context = MigrationContext.configure(
            connection=sync_connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
                "include_schemas": False,
            },
        )
        return compare_metadata(context, Base.metadata)

    async with engine.connect() as connection:
        diffs = await connection.run_sync(_compare)

    model_tables = set(Base.metadata.tables)
    print(f"models: {len(model_tables)} tables")

    if not diffs:
        print("Schema is in sync with the models.")
        return 0

    print(f"\n{len(diffs)} difference(s) detected:\n")
    for line in _describe(diffs):
        print(line)
    print(
        "\nResolve with a migration, never by editing the database:\n"
        '  cd backend && python -m alembic revision --autogenerate -m "describe change"\n'
        "  python -m alembic upgrade head"
    )
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(check()))
