"""Ad-hoc: reproduce the Redis connection failure with a full traceback."""

from __future__ import annotations

import asyncio
import traceback

from redis.asyncio import Redis


async def main() -> None:
    for url in ("redis://localhost:6379/0", "redis://127.0.0.1:6379/0"):
        client = Redis.from_url(url, socket_connect_timeout=2)
        try:
            print(url, "->", await client.ping())
        except Exception:
            print(url, "-> FAILED")
            traceback.print_exc()
        finally:
            await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
