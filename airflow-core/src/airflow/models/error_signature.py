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

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from airflow._shared.timezones import timezone
from airflow.models.base import Base
from airflow.utils.sqlalchemy import UtcDateTime, mapped_column


class ErrorSignature(Base):
    """Normalized signature for deduplicating structurally equivalent errors."""

    __tablename__ = "error_signature"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signature_canonical: Mapped[str] = mapped_column(Text, nullable=False)
    signature_regex: Mapped[str] = mapped_column(Text, nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=timezone.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=timezone.utcnow, onupdate=timezone.utcnow, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    notes = relationship("ErrorNote", back_populates="signature", cascade="all, delete-orphan")
