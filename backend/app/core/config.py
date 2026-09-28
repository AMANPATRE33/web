"""Application configuration.

Every tunable in the system is declared here so that the full surface of
required environment variables is discoverable in one place. Settings are
immutable at runtime and validated eagerly, which means a misconfigured deploy
fails at boot rather than on the first customer request.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]
TaxMode = Literal["inclusive", "exclusive"]
#: How a GST invoice breaks the tax down. See `tax_split_mode` below.
TaxSplitMode = Literal["INTRA_STATE", "INTER_STATE"]
EmailProvider = Literal["console", "resend", "ses", "smtp"]

# Repository root: backend/app/core/config.py -> app/core -> app -> backend -> root
REPO_ROOT = Path(__file__).resolve().parents[3]

# Secrets that must never be left at their placeholder value in production.
_PLACEHOLDER_SECRETS = {
    "change-me-to-48-random-characters-minimum",
    "changeme",
    "secret",
    "test",
}


def _split_csv(value: str | list[str] | None) -> list[str]:
    """Normalise a comma separated setting into a clean list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----------------------------------------------------------------- app
    app_env: Environment = "development"
    app_name: str = "storefront-api"
    log_level: str = "INFO"
    debug: bool = False

    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # ------------------------------------------------------------ database
    database_url: SecretStr = Field(
        # Default points at the isolated throwaway cluster created by
        # scripts/local-postgres.ps1, never at a developer's own Postgres on
        # 5432. A missing .env must fail loudly, not quietly write to an
        # unrelated database.
        default="postgresql+asyncpg://storefront:storefront_dev_only@127.0.0.1:55432/storefront"
    )
    database_read_url: SecretStr | None = None
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_echo: bool = False
    db_statement_timeout_ms: int = 15000

    # ------------------------------------------------------------ supabase
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_role_key: SecretStr = SecretStr("")
    supabase_publishable_key: SecretStr = SecretStr("")
    # Optional for asymmetric (ES256/RS256) projects, required for legacy HS256.
    supabase_jwt_secret: SecretStr | None = None
    supabase_storage_bucket: str = "product-images"
    supabase_redirect_urls: str = "http://localhost:3000/auth/callback"

    # --------------------------------------------------------------- auth
    jwt_secret: SecretStr = SecretStr("change-me-to-48-random-characters-minimum")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    security_headers_enabled: bool = True
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_auth_requests: int = 8
    rate_limit_write_requests: int = 30

    # ----------------------------------------------------------- razorpay
    razorpay_key_id: str = ""
    razorpay_key_secret: SecretStr = SecretStr("")
    razorpay_webhook_secret: SecretStr = SecretStr("")
    razorpay_mode: Literal["test", "live"] = "test"
    razorpay_capture_method: str = "automatic"
    #: Whether this deployment takes payments.
    #:
    #: False (the default) because the checkout -> order -> payment pipeline is
    #: not built yet. While False, the three Razorpay variables are not required
    #: to boot and no payment route exists to misconfigure. Set it to True in the
    #: same deploy that adds payment handling, and the credentials become
    #: mandatory - the check is gated on the feature, not deleted.
    payments_enabled: bool = False
    payment_intent_ttl_seconds: int = 900
    refund_requires_confirmation_above: float = 5000.00

    # -------------------------------------------------------------- email
    email_provider: EmailProvider = "console"
    email_from_name: str = "Storefront"
    email_from_email: str = "orders@example.com"
    email_reply_to: str = "support@example.com"
    resend_api_key: SecretStr = SecretStr("")
    aws_region: str = "ap-south-1"
    aws_access_key_id: SecretStr = SecretStr("")
    aws_secret_access_key: SecretStr = SecretStr("")
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_use_tls: bool = True

    # -------------------------------------------------------------- redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_db: int = 0
    redis_job_db: int = 1
    worker_concurrency: int = 10
    job_abandoned_cart_hours: int = 6
    job_analytics_cron: str = "17 3 * * *"
    job_newsletter_digest_cron: str = "23 7 * * 1"
    job_low_stock_report_cron: str = "41 8 * * *"

    # ---------------------------------------------------- catalogue policy
    currency: str = "INR"
    currency_symbol: str = "Rs."
    # A **fraction**, not a percentage: 0.18 means 18%. It is converted to
    # integer basis points exactly once, in `services.pricing.rate_to_bps`, via
    # `Decimal(str(...))` so the float literal a human typed is never the thing
    # that gets multiplied by a cart subtotal.
    tax_mode: TaxMode = "inclusive"
    tax_rate: float = 0.18
    tax_inclusive_label: str = "incl. all taxes"
    # Which GST breakdown an invoice carries. A GST invoice must show CGST/SGST
    # for an intra-state supply and IGST for an inter-state one, and we store the
    # customer's state as free text rather than a state code, so place of supply
    # cannot be derived reliably. Making it explicit configuration is the
    # honest option; guessing would be a compliance risk on a tax document.
    # The applied value is written to `orders.tax_split_mode` so a historical
    # invoice can be reproduced after this setting changes.
    tax_split_mode: TaxSplitMode = "INTRA_STATE"
    shipping_flat_rate: float = 99.00
    shipping_free_above: float = 4999.00
    cart_abandoned_after_minutes: int = 360
    order_retention_days: int = 730

    # ------------------------------------------------------------ uploads
    upload_max_bytes: int = 5 * 1024 * 1024
    upload_allowed_mime_types: str = "image/jpeg,image/png,image/webp,image/avif"
    upload_signed_url_ttl_seconds: int = 3600

    # ------------------------------------------------------------ derived
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return _split_csv(self.cors_origins)

    @property
    def redirect_url_list(self) -> list[str]:
        return _split_csv(self.supabase_redirect_urls)

    @property
    def allowed_upload_mime_types(self) -> set[str]:
        return set(_split_csv(self.upload_allowed_mime_types))

    @property
    def effective_database_url(self) -> str:
        return self.database_url.get_secret_value()

    @property
    def effective_read_database_url(self) -> str:
        if self.database_read_url is not None:
            return self.database_read_url.get_secret_value()
        return self.effective_database_url

    @property
    def razorpay_is_configured(self) -> bool:
        return bool(self.razorpay_key_id) and bool(self.razorpay_key_secret.get_secret_value())

    @property
    def supabase_is_configured(self) -> bool:
        return bool(self.supabase_service_role_key.get_secret_value())

    @property
    def redis_job_url(self) -> str:
        """Redis URL pointing at the job queue database index."""
        return _with_db_index(self.redis_url, self.redis_job_db)

    @property
    def redis_cache_url(self) -> str:
        return _with_db_index(self.redis_url, self.redis_cache_db)

    @property
    def api_docs_url(self) -> str | None:
        # Public API docs are a liability in production: they enumerate every
        # route and schema. Only serve them outside production, or when the
        # operator has explicitly re-enabled debug mode.
        if self.is_production and not self.debug:
            return None
        return "/api/docs"

    @property
    def api_redoc_url(self) -> str | None:
        if self.is_production and not self.debug:
            return None
        return "/api/redoc"

    # ---------------------------------------------------------- validators
    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid LOG_LEVEL: {value!r}")
        return level

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_cors(cls, value: str) -> str:
        origins = _split_csv(value)
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS must not contain '*'. List explicit origins, e.g. "
                "CORS_ORIGINS=https://shop.example.com"
            )
        return value

    @model_validator(mode="after")
    def _production_safety_rails(self) -> Settings:
        if not self.is_production:
            return self

        problems: list[str] = []

        if _PLACEHOLDER_SECRETS & {self.jwt_secret.get_secret_value()}:
            problems.append("JWT_SECRET is still the placeholder value")
        if len(self.jwt_secret.get_secret_value()) < 32:
            problems.append("JWT_SECRET must be at least 32 characters")
        if not self.cors_origin_list:
            problems.append("CORS_ORIGINS must list explicit production origins")
        if self.cors_origin_list and all(
            origin.startswith("http://localhost") for origin in self.cors_origin_list
        ):
            problems.append("CORS_ORIGINS still points at localhost in production")
        if not self.supabase_service_role_key.get_secret_value():
            problems.append("SUPABASE_SERVICE_ROLE_KEY is required in production")
        # Razorpay is only required when payments are switched on. The payment
        # pipeline is not built yet, so demanding three gateway credentials to
        # boot a catalogue-only deployment blocks the one deploy that is actually
        # useful, and trains people to paste placeholder secrets to get past it -
        # which is a worse outcome than an unconfigured feature.
        #
        # This is opt-in, not opt-out: `payments_enabled` defaults to False, and
        # setting it True restores the full requirement. Nothing is weakened for
        # a deployment that takes money, because such a deployment has to say so
        # explicitly before the check is skipped.
        if self.payments_enabled:
            if not self.razorpay_is_configured:
                problems.append(
                    "PAYMENTS_ENABLED is set, so RAZORPAY_KEY_ID and "
                    "RAZORPAY_KEY_SECRET are required"
                )
            if not self.razorpay_webhook_secret.get_secret_value():
                problems.append(
                    "PAYMENTS_ENABLED is set, so RAZORPAY_WEBHOOK_SECRET is required"
                )
        if "localhost" in self.frontend_url or "localhost" in self.backend_url:
            problems.append("FRONTEND_URL / BACKEND_URL still point at localhost")
        if not self.tax_mode:
            problems.append("TAX_MODE must be set")

        if problems:
            raise ValueError(
                "Refusing to start in production with an unsafe configuration:\n  - "
                + "\n  - ".join(problems)
            )
        return self


def _with_db_index(redis_url: str, index: int) -> str:
    """Return the Redis URL with the database index replaced."""
    base, sep, tail = redis_url.rpartition("/")
    if not sep or not tail.isdigit():
        return redis_url
    return f"{base}/{index}"


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so that validation runs once. Tests can call ``get_settings.cache_clear()``
    after mutating the environment.
    """
    return Settings()


settings = get_settings()
