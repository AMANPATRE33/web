"""Dump real API responses so the frontend can be typed against actual data.

Run:  python -m app.scripts.dump_api_contract
Writes:  .local/api-contract/*.json  (git-ignored)

This is a development aid, not a fixture. The point is to type the TypeScript
client against what the API *actually* returns, including the null cases and
the exact envelope shape, rather than against an assumption.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from app.main import create_app
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / ".local" / "api-contract"

REQUESTS: list[tuple[str, str, dict[str, Any]]] = [
    ("products_page1", "/api/v1/products", {"per_page": 2, "sort": "newest"}),
    (
        "products_filtered",
        "/api/v1/products",
        {
            "per_page": 2,
            "category": "electrical-safety",
            "material": "3MM ACP",
            "in_stock": True,
        },
    ),
    ("product_detail", "/api/v1/products/danger-high-voltage", {}),
    ("product_related", "/api/v1/products/danger-high-voltage/related", {"limit": 2}),
    ("categories", "/api/v1/categories", {}),
    ("category_detail", "/api/v1/categories/electrical-safety", {}),
    ("category_facets", "/api/v1/categories/electrical-safety/facets", {}),
    ("global_facets", "/api/v1/facets", {}),
    ("search", "/api/v1/search", {"q": "electrical"}),
    ("search_suggestions", "/api/v1/search/suggestions", {"q": "dang"}),
    ("featured", "/api/v1/products/featured", {"limit": 2}),
    ("new_arrivals", "/api/v1/products/new", {"limit": 2}),
    ("filter_schema", "/api/v1/filters", {}),
]


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://contract") as client:
        for name, path, params in REQUESTS:
            try:
                response = await client.get(path, params=params)
            except Exception as exc:
                print(f"FAIL {name}: {exc}")
                continue

            body: Any
            try:
                body = response.json()
            except ValueError:
                body = {"_raw": response.text[:500]}

            payload = {"status": response.status_code, "body": body}
            (OUT_DIR / f"{name}.json").write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
            print(f"{response.status_code} {name:24} -> {len(json.dumps(body, default=str))} bytes")

    # Print the product detail in full: it is the contract the PDP depends on.
    detail_file = OUT_DIR / "product_detail.json"
    if detail_file.exists():
        data = json.loads(detail_file.read_text(encoding="utf-8"))
        print("\n--- product detail keys ---")
        print(sorted(data["body"].keys()))
        print("--- first variant ---")
        variants = data["body"].get("variants") or []
        if variants:
            print(json.dumps(variants[0], indent=2, default=str))
        print("--- options ---")
        print(json.dumps(data["body"].get("options"), indent=2, default=str)[:900])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
