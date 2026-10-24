"""Patient height and weight (BMI is calculated from them).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("patient_profiles")}
    with op.batch_alter_table("patient_profiles") as b:
        if "height_cm" not in cols:
            b.add_column(sa.Column("height_cm", sa.Float(), nullable=True))
        if "weight_kg" not in cols:
            b.add_column(sa.Column("weight_kg", sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table("patient_profiles") as b:
        b.drop_column("weight_kg")
        b.drop_column("height_cm")
