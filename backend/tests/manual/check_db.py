"""Ad-hoc: reproduce the database connection failure with the real error."""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.session import get_engine


async def main() -> None:
    settings = get_settings()
    print("url:", settings.effective_database_url)
    engine = get_engine(settings)
    try:
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql("select 1 as ok")
            print("raw connect OK:", result.fetchall())
    except Exception as exc:  # noqa: BLE001
        print("FAILED:", type(exc).__name__)
        print(exc)


if __name__ == "__main__":
    asyncio.run(main())
