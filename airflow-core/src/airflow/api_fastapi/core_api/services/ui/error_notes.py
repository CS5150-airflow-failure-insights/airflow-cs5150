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

import re

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from airflow._shared.timezones import timezone
from airflow.models.error_note import ErrorNote
from airflow.models.error_signature import ErrorSignature
from airflow.utils.error_signature import (
    create_signature_canonical,
    create_signature_hash,
    create_signature_regex,
    normalize_highlighted_text,
)


class ErrorNotesService:
    """CRUD + signature-resolution service for error notes."""

    @staticmethod
    def resolve_error_signature_id(session: Session, highlighted_text: str) -> int:
        normalized_text = normalize_highlighted_text(highlighted_text)
        signature_canonical = create_signature_canonical(normalized_text)
        signature_hash = create_signature_hash(signature_canonical)
        generated_regex = create_signature_regex(signature_canonical)

        candidates = session.scalars(
            select(ErrorSignature).where(
                and_(ErrorSignature.signature_hash == signature_hash, ErrorSignature.is_active.is_(True))
            )
        ).all()
        for candidate in candidates:
            if re.search(candidate.signature_regex, normalized_text):
                return candidate.id

        signature = ErrorSignature(
            signature_canonical=signature_canonical,
            signature_regex=generated_regex,
            signature_hash=signature_hash,
            is_active=True,
        )
        session.add(signature)
        session.flush()
        return signature.id

    @staticmethod
    def create_note(
        session: Session,
        highlighted_text: str,
        author: str,
        note_text: str,
        external_url: str | None,
    ) -> ErrorNote:
        signature_id = ErrorNotesService.resolve_error_signature_id(
            session=session, highlighted_text=highlighted_text
        )
        note = ErrorNote(
            signature_id=signature_id,
            author=author,
            note_text=note_text,
            external_url=external_url,
            is_deleted=False,
        )
        session.add(note)
        session.flush()
        return note

    @staticmethod
    def list_notes_for_highlighted_text(session: Session, highlighted_text: str) -> list[ErrorNote]:
        signature_id = ErrorNotesService.resolve_error_signature_id(
            session=session, highlighted_text=highlighted_text
        )
        return session.scalars(
            select(ErrorNote)
            .where(and_(ErrorNote.signature_id == signature_id, ErrorNote.is_deleted.is_(False)))
            .order_by(ErrorNote.created_at.asc())
        ).all()

    @staticmethod
    def update_note(session: Session, note_id: int, note_text: str) -> ErrorNote | None:
        note = session.scalar(select(ErrorNote).where(ErrorNote.id == note_id))
        if note is None or note.is_deleted:
            return None
        note.note_text = note_text
        note.updated_at = timezone.utcnow()
        session.flush()
        return note

    @staticmethod
    def soft_delete_note(session: Session, note_id: int) -> bool:
        note = session.scalar(select(ErrorNote).where(ErrorNote.id == note_id))
        if note is None or note.is_deleted:
            return False
        note.is_deleted = True
        note.updated_at = timezone.utcnow()
        session.flush()
        return True
