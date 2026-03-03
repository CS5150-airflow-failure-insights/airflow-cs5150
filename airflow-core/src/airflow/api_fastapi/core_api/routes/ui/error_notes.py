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
)
from airflow.api_fastapi.core_api.openapi.exceptions import create_openapi_http_exception_doc
from airflow.api_fastapi.core_api.security import requires_authenticated
from airflow.api_fastapi.core_api.services.ui.error_notes import ErrorNotesService

error_notes_router = AirflowRouter(tags=["Error Note"], prefix="/error-notes")


@error_notes_router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requires_authenticated())],
)
def create_error_note(
    body: ErrorNoteCreateBody,
    session: SessionDep,
) -> ErrorNoteResponse:
    note = ErrorNotesService.create_note(
        session=session,
        highlighted_text=body.highlighted_text,
        author=body.author,
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
    notes = ErrorNotesService.list_notes_for_highlighted_text(
        session=session, highlighted_text=body.highlighted_text
    )
    return ErrorNoteCollectionResponse(notes=notes, total_entries=len(notes))


@error_notes_router.patch(
    path="/{note_id}",
    responses=create_openapi_http_exception_doc([status.HTTP_404_NOT_FOUND]),
    dependencies=[Depends(requires_authenticated())],
)
def update_error_note(
    note_id: int,
    body: ErrorNotePatchBody,
    session: SessionDep,
) -> ErrorNoteResponse:
    note = ErrorNotesService.update_note(session=session, note_id=note_id, note_text=body.note_text)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Error note not found")
    return note


@error_notes_router.delete(
    path="/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=create_openapi_http_exception_doc([status.HTTP_404_NOT_FOUND]),
    dependencies=[Depends(requires_authenticated())],
)
def delete_error_note(
    note_id: int,
    session: SessionDep,
) -> None:
    success = ErrorNotesService.soft_delete_note(session=session, note_id=note_id)
    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Error note not found")
