"""API v1 root router.

Every feature module is mounted here. Keep the import list explicit so that a
missing module fails at boot rather than on the first request that needs it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app import __version__
from app.api.v1.account import router as account_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.cart import router as cart_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.content import router as content_router

router = APIRouter()


@router.get("/", summary="API index")
async def api_index() -> dict[str, Any]:
    """Machine readable index of the mounted resource groups."""
    return {
        "name": "storefront-api",
        "version": __version__,
        "resources": {
            "catalog": "/api/v1/products, /api/v1/categories, /api/v1/search",
            "content": "/api/v1/industries, /api/v1/blog/posts",
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


# --- public catalogue -------------------------------------------------------
router.include_router(catalog_router, tags=["catalog"])

# --- cart (guest cookie or authenticated) ---------------------------------
router.include_router(cart_router)
router.include_router(content_router, tags=["content"])

# --- account (customer self-service) ---------------------------------------
router.include_router(account_router, prefix="/account", tags=["account"])

# --- admin (staff only; guarded at router level) ---------------------------
router.include_router(admin_users_router)
