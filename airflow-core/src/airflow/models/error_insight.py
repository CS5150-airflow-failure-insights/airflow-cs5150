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
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship

from airflow._shared.timezones import timezone
from airflow.models.base import Base
from airflow.utils.sqlalchemy import UtcDateTime, mapped_column


class ErrorSignature(Base):
    """Stores one distinct normalized error signature/pattern."""

    __tablename__ = "error_signature"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_regex: Mapped[str] = mapped_column(Text, nullable=False)
    signature_canonical: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=timezone.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=timezone.utcnow, onupdate=timezone.utcnow, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    notes = relationship("ErrorNote", back_populates="signature", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("signature_hash", name="idx_error_signature_hash_unique"),
        Index("idx_error_signature_is_active", "is_active"),
        Index("idx_error_signature_updated_at", "updated_at"),
    )


class ErrorNote(Base):
    """Stores annotations attached to an error signature."""

    __tablename__ = "error_note"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    signature_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("error_signature.id", name="error_note_signature_id_fkey", ondelete="CASCADE"),
        nullable=False,
    )
    author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=timezone.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=timezone.utcnow, onupdate=timezone.utcnow, nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    signature = relationship("ErrorSignature", back_populates="notes")

    __table_args__ = (
        Index("idx_error_note_signature_id", "signature_id"),
        Index("idx_error_note_created_at", "created_at"),
        Index("idx_error_note_is_deleted", "is_deleted"),
    )
