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

import pytest
from sqlalchemy import delete, func, select

from airflow.models.error_note import ErrorNote
from airflow.models.error_signature import ErrorSignature

pytestmark = pytest.mark.db_test

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from airflow.models.base import Base
from airflow.models.error_note import ErrorNote
from airflow.models.error_signature import ErrorSignature

from airflow.models.base import Base
from airflow.utils.session import create_session
from airflow.settings import engine

from airflow.utils.db import initdb
import pytest


@pytest.fixture(scope="session", autouse=True)
def airflow_db():
    initdb()


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")

    # Only create the tables needed for these tests
    ErrorSignature.__table__.create(engine)
    ErrorNote.__table__.create(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()

@pytest.fixture(autouse=True)
def clean_db(session):
    session.execute(delete(ErrorNote))
    session.execute(delete(ErrorSignature))
    session.commit()
    yield
    session.execute(delete(ErrorNote))
    session.execute(delete(ErrorSignature))
    session.commit()


class TestErrorNotesRoutes:
    def test_full_crud_flow(self, test_client, session):
        highlighted_text = "KeyError: 'token_4876' in /tmp/run_2026-03-03.log"

        lookup_response_1 = test_client.post(
            "/error-notes/lookup", json={"highlighted_text": highlighted_text}
        )
        assert lookup_response_1.status_code == 200
        assert lookup_response_1.json() == {"notes": [], "total_entries": 0}

        create_response_1 = test_client.post(
            "/error-notes",
            json={
                "highlighted_text": highlighted_text,
                "author": "lms444",
                "note_text": "Likely stale token. Rotate secret and re-run.",
                "external_url": "https://internal/wiki/token-runbook",
            },
        )
        assert create_response_1.status_code == 201
        note_1 = create_response_1.json()
        note_id_1 = note_1["note_id"]

        create_response_2 = test_client.post(
            "/error-notes",
            json={
                "highlighted_text": highlighted_text,
                "author": "kap272",
                "note_text": "Confirmed, fixed by updating env var.",
            },
        )
        assert create_response_2.status_code == 201
        note_2 = create_response_2.json()
        note_id_2 = note_2["note_id"]
        assert note_id_1 != note_id_2

        signature_count = session.scalar(select(func.count()).select_from(ErrorSignature))
        note_count = session.scalar(select(func.count()).select_from(ErrorNote))
        assert signature_count == 1
        assert note_count == 2

        lookup_response_2 = test_client.post(
            "/error-notes/lookup", json={"highlighted_text": highlighted_text}
        )
        assert lookup_response_2.status_code == 200
        payload = lookup_response_2.json()
        assert payload["total_entries"] == 2
        assert {row["note_id"] for row in payload["notes"]} == {note_id_1, note_id_2}

        patch_response = test_client.patch(
            f"/error-notes/{note_id_1}",
            json={"note_text": "Root cause: expired service token. Refresh token."},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["note_text"] == "Root cause: expired service token. Refresh token."

        delete_response = test_client.delete(f"/error-notes/{note_id_2}")
        assert delete_response.status_code == 204

        deleted_note = session.scalar(select(ErrorNote).where(ErrorNote.id == note_id_2))
        assert deleted_note is not None
        assert deleted_note.is_deleted is True

        lookup_response_3 = test_client.post(
            "/error-notes/lookup", json={"highlighted_text": highlighted_text}
        )
        assert lookup_response_3.status_code == 200
        payload_after_delete = lookup_response_3.json()
        assert payload_after_delete["total_entries"] == 1
        assert [row["note_id"] for row in payload_after_delete["notes"]] == [note_id_1]

    def test_patch_missing_note_returns_404(self, test_client):
        response = test_client.patch("/error-notes/999999", json={"note_text": "new text"})
        assert response.status_code == 404

    def test_delete_missing_note_returns_404(self, test_client):
        response = test_client.delete("/error-notes/999999")
        assert response.status_code == 404

    def test_auth_required(self, unauthenticated_test_client):
        response = unauthenticated_test_client.post(
            "/error-notes/lookup", json={"highlighted_text": "KeyError: token_1111"}
        )
        assert response.status_code == 401
        
    def test_lookup_creates_signature_if_missing(self, test_client, session):
        text = "ValueError: invalid token_1234 in /tmp/file.log"

        response = test_client.post(
            "/error-notes/lookup",
            json={"highlighted_text": text},
        )

        assert response.status_code == 200
        assert response.json()["total_entries"] == 0

        signature_count = session.scalar(select(func.count()).select_from(ErrorSignature))
        assert signature_count == 1
    def test_similar_errors_share_same_signature(self, test_client, session):
        text_a = "KeyError token_1111 at /tmp/run_2026-01-01.log"
        text_b = "KeyError token_9999 at /tmp/run_2026-02-02.log"

        test_client.post(
            "/error-notes",
            json={
                "highlighted_text": text_a,
                "author": "a",
                "note_text": "first note",
            },
        )

        test_client.post(
            "/error-notes",
            json={
                "highlighted_text": text_b,
                "author": "b",
                "note_text": "second note",
            },
        )

        signature_count = session.scalar(select(func.count()).select_from(ErrorSignature))
        assert signature_count == 1    

    def test_different_errors_create_different_signatures(self, test_client, session):
        text_a = "KeyError token_1111 at /tmp/run.log"
        text_b = "ValueError invalid value at /tmp/run.log"

        test_client.post(
            "/error-notes",
            json={
                "highlighted_text": text_a,
                "author": "user",
                "note_text": "note a",
            },
        )

        test_client.post(
            "/error-notes",
            json={
                "highlighted_text": text_b,
                "author": "user",
                "note_text": "note b",
            },
        )

        signature_count = session.scalar(select(func.count()).select_from(ErrorSignature))
        assert signature_count == 2    

    def test_soft_deleted_notes_not_returned(self, test_client, session):
        text = "IndexError list index out of range token_123"

        create = test_client.post(
            "/error-notes",
            json={
                "highlighted_text": text,
                "author": "user",
                "note_text": "debug note",
            },
        )

        note_id = create.json()["note_id"]

        test_client.delete(f"/error-notes/{note_id}")

        lookup = test_client.post(
            "/error-notes/lookup",
            json={"highlighted_text": text},
        )

        assert lookup.status_code == 200
        assert lookup.json()["total_entries"] == 0    

    def test_notes_returned_in_creation_order(self, test_client):
        text = "RuntimeError worker failure token_111"

        r1 = test_client.post(
            "/error-notes",
            json={"highlighted_text": text, "author": "a", "note_text": "first"},
        )

        r2 = test_client.post(
            "/error-notes",
            json={"highlighted_text": text, "author": "b", "note_text": "second"},
        )

        lookup = test_client.post(
            "/error-notes/lookup",
            json={"highlighted_text": text},
        )

        notes = lookup.json()["notes"]

        assert notes[0]["note_id"] == r1.json()["note_id"]
        assert notes[1]["note_id"] == r2.json()["note_id"]    

    def test_external_url_optional(self, test_client):
        text = "ConnectionError token_777"

        response = test_client.post(
            "/error-notes",
            json={
                "highlighted_text": text,
                "author": "user",
                "note_text": "no url provided",
            },
        )

        assert response.status_code == 201
        assert response.json()["external_url"] is None    