"""required PostgreSQL extensions

Revision ID: 0000_extensions
Revises:
Created: 2026-09-27

Every database that runs this migration chain - a fresh Supabase project, a CI
container, a developer's local cluster - must end up with the same extensions,
or the schema migration fails on ``type "citext" does not exist``. Supabase
installs these by default, so ``IF NOT EXISTS`` makes this a no-op there while
still provisioning them everywhere else.

* ``pgcrypto``   - ``gen_random_uuid()``; Supabase pins this to the extensions
                   schema, which is why the API's connect hook sets
                   ``search_path = public, extensions``.
* ``citext``     - case-insensitive email equality for ``profiles`` and
                   ``newsletter_subscribers``, so ``A@x.com`` and ``a@x.com``
                   cannot both register.
* ``pg_trgm``    - trigram indexes for fuzzy product search ("headfone").
* ``btree_gin``  - lets GIN and btree be combined in one index, used for
                   combined tag + status + price filtering on listings.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0000_extensions"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: (extension, schema or None for default)
_EXTENSIONS = (
    ("pgcrypto", "extensions"),
    ("citext", None),
    ("pg_trgm", None),
    ("btree_gin", None),
)


def _current_database_name() -> str:
    """Resolve the connected database name.

    ``ALTER DATABASE`` requires a literal identifier; ``CURRENT_DATABASE`` is
    parsed as the name of a database called "current_database" rather than as a
    function call, so the name has to be read from the connection first.
    """
    result = op.get_bind().execute(sa.text("SELECT current_database()"))
    return str(result.scalar_one())


def upgrade() -> None:
    for extension, schema in _EXTENSIONS:
        # A dedicated schema keeps Supabase's managed extensions out of
        # `public`, which avoids permission surprises for the app role.
        if schema:
            op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension} WITH SCHEMA {schema}")
        else:
            op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}")

    # The API resolves gen_random_uuid() through this path.
    database_name = _current_database_name().replace('"', '""')
    op.execute(f'ALTER DATABASE "{database_name}" SET search_path = public, extensions')


def downgrade() -> None:
    # Extensions are intentionally left installed. Dropping citext would fail
    # if any column still uses the type, and a downgrade of a bootstrap
    # migration should not destroy shared database-level capability.
    pass
