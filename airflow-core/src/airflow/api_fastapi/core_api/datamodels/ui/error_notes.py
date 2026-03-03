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

from pydantic import Field

from airflow.api_fastapi.core_api.base import BaseModel, StrictBaseModel


class ErrorNoteCreateBody(StrictBaseModel):
    highlighted_text: str = Field(min_length=1)
    author: str = Field(min_length=1, max_length=250)
    note_text: str = Field(min_length=1)
    external_url: str | None = None


class ErrorNoteLookupBody(StrictBaseModel):
    highlighted_text: str = Field(min_length=1)


class ErrorNotePatchBody(StrictBaseModel):
    note_text: str = Field(min_length=1)


class ErrorNoteResponse(BaseModel):
    note_id: int = Field(serialization_alias="note_id", validation_alias="id")
    signature_id: int
    author: str
    note_text: str
    external_url: str | None
    created_at: datetime
    updated_at: datetime


class ErrorNoteCollectionResponse(BaseModel):
    notes: list[ErrorNoteResponse]
    total_entries: int
