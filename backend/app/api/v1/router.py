"""API v1 root router.

Every feature module is mounted here. Keep the import list explicit so that a
missing module fails at boot rather than on the first request that needs it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app import __version__

router = APIRouter()


@router.get("/", summary="API index")
async def api_index() -> dict[str, Any]:
    """Machine readable index of the mounted resource groups."""
    return {
        "name": "storefront-api",
        "version": __version__,
        "resources": {
            "catalog": "/api/v1/products, /api/v1/categories, /api/v1/search",
            "cart": "/api/v1/cart",
            "wishlist": "/api/v1/wishlist",
            "checkout": "/api/v1/checkout",
            "payments": "/api/v1/payments",
            "orders": "/api/v1/orders",
            "account": "/api/v1/account",
            "reviews": "/api/v1/reviews",
            "admin": "/api/v1/admin",
        },
    }
