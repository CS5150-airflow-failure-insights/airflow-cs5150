#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Add error signature and error note tables.

Revision ID: 6d58f39f2cb1
Revises: 82dbd68e6171
Create Date: 2026-03-03 14:25:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6d58f39f2cb1"
down_revision = "82dbd68e6171"
branch_labels = None
depends_on = None
airflow_version = "3.2.0"


def upgrade():
    """Create error signature and error note tables."""
    op.create_table(
        "error_signature",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("signature_canonical", sa.Text(), nullable=False),
        sa.Column("signature_regex", sa.Text(), nullable=False),
        sa.Column("signature_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id", name=op.f("error_signature_pkey")),
        sa.UniqueConstraint("signature_hash", name=op.f("error_signature_signature_hash_uq")),
    )
    with op.batch_alter_table("error_signature", schema=None) as batch_op:
        batch_op.create_index(op.f("idx_error_signature_signature_hash"), ["signature_hash"], unique=True)

    op.create_table(
        "error_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("signature_id", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=250), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["signature_id"],
            ["error_signature.id"],
            name=op.f("error_note_signature_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("error_note_pkey")),
    )
    with op.batch_alter_table("error_note", schema=None) as batch_op:
        batch_op.create_index(op.f("idx_error_note_signature_id"), ["signature_id"], unique=False)


def downgrade():
    """Drop error signature and error note tables."""
    with op.batch_alter_table("error_note", schema=None) as batch_op:
        batch_op.drop_index(op.f("idx_error_note_signature_id"))
    op.drop_table("error_note")

    with op.batch_alter_table("error_signature", schema=None) as batch_op:
        batch_op.drop_index(op.f("idx_error_signature_signature_hash"))
    op.drop_table("error_signature")
