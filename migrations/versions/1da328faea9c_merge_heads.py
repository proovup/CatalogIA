"""Merge heads

Revision ID: 1da328faea9c
Revises: e8f1a2b3c4d5, c3d4e5f6a7b8
Create Date: 2026-03-29 16:24:39.526507

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1da328faea9c'
down_revision: Union[str, None] = ('e8f1a2b3c4d5', 'c3d4e5f6a7b8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
