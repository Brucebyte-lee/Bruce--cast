"""create favorites and preferences

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("client_id", "latitude", "longitude", name="uq_favorite_client_coords"),
    )
    op.create_index("ix_favorites_client_id", "favorites", ["client_id"])
    op.create_table(
        "preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("temperature_unit", sa.String(10), nullable=False),
        sa.Column("unit_system", sa.String(10), nullable=False),
        sa.Column("theme", sa.String(10), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_preferences_client_id", "preferences", ["client_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_preferences_client_id", table_name="preferences")
    op.drop_table("preferences")
    op.drop_index("ix_favorites_client_id", table_name="favorites")
    op.drop_table("favorites")
