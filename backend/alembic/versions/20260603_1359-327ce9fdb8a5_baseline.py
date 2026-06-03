"""baseline

Revision ID: 327ce9fdb8a5
Revises: 
Create Date: 2026-06-03 13:59:02.087316

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '327ce9fdb8a5'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
