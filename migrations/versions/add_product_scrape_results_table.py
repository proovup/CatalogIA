"""add product_scrape_results table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-12 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_scrape_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_site", sa.String(255), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("characteristics", postgresql.JSONB(), nullable=True),
        sa.Column("images", postgresql.JSONB(), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_product_scrape_results_product_id", "product_scrape_results", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_product_scrape_results_product_id", table_name="product_scrape_results")
    op.drop_table("product_scrape_results")
