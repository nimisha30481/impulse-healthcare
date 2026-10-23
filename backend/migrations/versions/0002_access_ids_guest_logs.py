"""Patient Access IDs + guest access log.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""
import secrets
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

import app.models  # noqa: F401
from app.models import GuestAccessLog

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def upgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("patient_profiles")}
    with op.batch_alter_table("patient_profiles") as b:
        if "access_id" not in cols:
            b.add_column(sa.Column("access_id", sa.String(16), nullable=True))
        if "access_id_created_at" not in cols:
            b.add_column(sa.Column("access_id_created_at", sa.DateTime(timezone=True), nullable=True))
    if "ix_patient_profiles_access_id" not in {i["name"] for i in sa.inspect(bind).get_indexes("patient_profiles")}:
        op.create_index("ix_patient_profiles_access_id", "patient_profiles", ["access_id"], unique=True)
    GuestAccessLog.__table__.create(bind, checkfirst=True)

    # give every existing patient an Access ID
    used = set()
    rows = bind.execute(sa.text("SELECT id, mrn FROM patient_profiles WHERE access_id IS NULL")).fetchall()
    now = datetime.now(timezone.utc)
    demo = {"IMP-DEMO-0001": "DW-ANANYA", "IMP-DEMO-0002": "DW-RAHULV", "IMP-DEMO-0003": "DW-MEERA2"}
    for pid, mrn in rows:
        code = demo.get(mrn)
        while code is None or code in used:
            code = "DW-" + "".join(secrets.choice(ALPHABET) for _ in range(6))
        used.add(code)
        bind.execute(sa.text("UPDATE patient_profiles SET access_id=:c, access_id_created_at=:t WHERE id=:i"),
                     {"c": code, "t": now, "i": pid})


def downgrade():
    op.drop_table("guest_access_logs")
    op.drop_index("ix_patient_profiles_access_id", "patient_profiles")
    with op.batch_alter_table("patient_profiles") as b:
        b.drop_column("access_id_created_at")
        b.drop_column("access_id")
