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

from fastapi import Depends, HTTPException, status

from airflow.api_fastapi.common.db.common import SessionDep
from airflow.api_fastapi.common.router import AirflowRouter
from airflow.api_fastapi.core_api.datamodels.ui.error_notes import (
    ErrorNoteCollectionResponse,
    ErrorNoteCreateBody,
    ErrorNoteLookupBody,
    ErrorNotePatchBody,
    ErrorNoteResponse,
    ErrorNoteWithSignatureCollectionResponse,
    ErrorNoteWithSignatureResponse,
    ErrorSignatureResolveBody,
    ErrorSignatureResolveResponse,
)
from airflow.api_fastapi.core_api.openapi.exceptions import create_openapi_http_exception_doc
from airflow.api_fastapi.core_api.security import GetUserDep, requires_authenticated
from airflow.api_fastapi.core_api.services.ui.error_notes import EXTERNAL_URL_UNSET, ErrorNotesService
from airflow.models.error_note import ErrorNote

error_notes_router = AirflowRouter(tags=["Error Note"], prefix="/error-notes")


def _error_note_with_signature(note: ErrorNote) -> ErrorNoteWithSignatureResponse:
    sig = note.signature
    return ErrorNoteWithSignatureResponse(
        note_id=note.id,
        error_signature_id=note.signature_id,
        author=note.author,
        note_text=note.note_text,
        external_url=note.external_url,
        created_at=note.created_at,
        updated_at=note.updated_at,
        signature_canonical=sig.signature_canonical,
        signature_regex=sig.signature_regex,
    )


@error_notes_router.get(
    path="",
    dependencies=[Depends(requires_authenticated())],
)
def list_all_error_notes_with_signatures(
    session: SessionDep,
) -> ErrorNoteWithSignatureCollectionResponse:
    """Contract §6: all non-deleted notes with ``signature_regex`` / ``signature_canonical`` for log matching."""
    notes = ErrorNotesService.list_all_notes_with_signatures(session=session)
    rows = [_error_note_with_signature(n) for n in notes]
    return ErrorNoteWithSignatureCollectionResponse(notes=rows, total_entries=len(rows))


@error_notes_router.post(
    path="/resolve-signature",
    dependencies=[Depends(requires_authenticated())],
)
def resolve_error_signature(
    body: ErrorSignatureResolveBody,
    session: SessionDep,
) -> ErrorSignatureResolveResponse:
    """Contract §5: run the resolution pipeline and return ``error_signature_id`` (creates row if needed)."""
    signature_id = ErrorNotesService.resolve_error_signature_id(
        session=session, highlighted_text=body.highlighted_text
    )
    return ErrorSignatureResolveResponse(error_signature_id=signature_id)


@error_notes_router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requires_authenticated())],
)
def create_error_note(
    body: ErrorNoteCreateBody,
    session: SessionDep,
    user: GetUserDep,
) -> ErrorNoteResponse:
    """Contract §1: persist note linked to signature from ``airflow.utils.error_signature`` pipeline."""
    note = ErrorNotesService.create_note(
        session=session,
        highlighted_text=body.highlighted_text,
        author=user.get_name(),
        note_text=body.note_text,
        external_url=body.external_url,
    )
    return note


@error_notes_router.post(
    path="/lookup",
    dependencies=[Depends(requires_authenticated())],
)
def lookup_error_notes(
    body: ErrorNoteLookupBody,
    session: SessionDep,
) -> ErrorNoteCollectionResponse:
    """Contract §2: resolve ``highlighted_text`` to a signature, then return that signature's notes."""
    notes = ErrorNotesService.list_notes_for_highlighted_text(
        session=session, highlighted_text=body.highlighted_text
    )
    return ErrorNoteCollectionResponse(notes=notes, total_entries=len(notes))


@error_notes_router.patch(
    path="/{note_id}",
    responses=create_openapi_http_exception_doc([status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]),
    dependencies=[Depends(requires_authenticated())],
)
def update_error_note(
    note_id: int,
    body: ErrorNotePatchBody,
    session: SessionDep,
    user: GetUserDep,
) -> ErrorNoteResponse:
    """Contract §3: update ``note_text`` for an existing note."""
    try:
        note = ErrorNotesService.update_note(
            session=session,
            note_id=note_id,
            note_text=body.note_text,
            editor=user.get_name(),
            external_url=body.external_url if "external_url" in body.model_fields_set else EXTERNAL_URL_UNSET,
        )
    except PermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the note author can edit this note")

    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Error note not found")
    return note


@error_notes_router.delete(
    path="/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=create_openapi_http_exception_doc([status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]),
    dependencies=[Depends(requires_authenticated())],
)
def delete_error_note(
    note_id: int,
    session: SessionDep,
    user: GetUserDep,
) -> None:
    """Contract §4: soft-delete (``is_deleted = true``)."""
    try:
        success = ErrorNotesService.soft_delete_note_as_author(
            session=session, note_id=note_id, editor=user.get_name()
        )
    except PermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the note author can delete this note")

    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Error note not found")
