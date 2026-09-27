"""Ad-hoc readiness probe check against the real local Postgres."""

from __future__ import annotations

import asyncio
import json

from app.main import create_app
from httpx import ASGITransport, AsyncClient


async def main() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health/ready")
        print("status_code:", response.status_code)
        print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
