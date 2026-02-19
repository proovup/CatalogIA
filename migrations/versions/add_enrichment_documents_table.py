"""add enrichment_documents table

Revision ID: e8f1a2b3c4d5
Revises: add_product_scrape_results_table
Create Date: 2026-02-16 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = "e8f1a2b3c4d5"
down_revision = None  # Will be set during first run
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrichment_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enrichment_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("extracted_data", JSONB, nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("match_confidence", sa.Float, nullable=True),
        sa.Column("match_method", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_enrichment_documents_product_id",
        "enrichment_documents",
        ["product_id"],
    )
    op.create_index(
        "ix_enrichment_documents_document_id",
        "enrichment_documents",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_enrichment_documents_document_id")
    op.drop_index("ix_enrichment_documents_product_id")
    op.drop_table("enrichment_documents")
