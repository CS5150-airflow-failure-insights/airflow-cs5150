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

from airflow.utils.error_signature import (
    create_signature_canonical,
    create_signature_hash,
    create_signature_regex,
    create_signature_regex_from_highlighted_text,
    normalize_highlighted_text,
)


def test_canonicalization_replaces_run_specific_tokens():
    text = (
        "[2026-02-22, 17:54:57] ERROR KeyError: token_4725 "
        'File "/Users/example/airflow/dags/error.py", line 15 '
        "run_id=1c5e3888-faf8-4f4c-9f88-6fbf8f9d2f5f"
    )
    canonical = create_signature_canonical(text)
    assert "<TS>" in canonical
    assert "<PATH>" in canonical
    assert "<UUID>" in canonical
    assert "token_<NUM>" in canonical


def test_http_status_code_is_not_normalized():
    text = "HTTP 404 from endpoint /api/foo after 3 retries"
    canonical = create_signature_canonical(text)
    assert "HTTP 404" in canonical
    assert "after <NUM> retries" in canonical


def test_regex_and_hash_are_deterministic():
    text_a = "KeyError token_4876 at /tmp/run_2026-03-03.log"
    text_b = "KeyError token_9321 at /tmp/run_2026-03-04.log"
    canonical_a = create_signature_canonical(text_a)
    canonical_b = create_signature_canonical(text_b)

    assert canonical_a == canonical_b
    assert create_signature_hash(canonical_a) == create_signature_hash(canonical_b)

    regex = create_signature_regex(canonical_a)
    assert re.search(regex, text_a)
    assert re.search(regex, text_b)


def test_uuid_normalization():
    text = "run_id=123e4567-e89b-12d3-a456-426614174000"
    canonical = create_signature_canonical(text)
    assert "<UUID>" in canonical


def test_timestamp_normalization():
    text = "2026-03-03 14:22:10 ERROR something failed"
    canonical = create_signature_canonical(text)
    assert "<TS>" in canonical


def test_path_normalization():
    text = 'File "/Users/test/project/file.py", line 12'
    canonical = create_signature_canonical(text)
    assert "<PATH>" in canonical


def test_regex_matches_equivalent_errors():
    text_a = "KeyError token_1111 at /tmp/run_2026.log"
    text_b = "KeyError token_2222 at /tmp/run_2027.log"

    canonical = create_signature_canonical(text_a)
    regex = create_signature_regex(canonical)

    assert re.search(regex, text_a)
    assert re.search(regex, text_b)


def test_create_signature_regex_from_highlighted_text_matches_composed_pipeline():
    text_a = "KeyError token_1111 at /tmp/run_2026.log"
    text_b = "KeyError token_2222 at /tmp/run_2027.log"
    expected = create_signature_regex(create_signature_canonical(text_a))
    assert create_signature_regex_from_highlighted_text(text_a) == expected
    assert re.search(create_signature_regex_from_highlighted_text(text_a), text_b)


def test_normalize_highlighted_text_collapses_whitespace():
    assert normalize_highlighted_text("  KeyError:\n  token_123\t at /tmp/file.log  ") == (
        "KeyError: token_123 at /tmp/file.log"
    )


def test_http_status_normalization_is_case_insensitive_and_preserves_each_code():
    text = "http 500 on /api/foo then HTTP 404 after 3 retries"
    canonical = create_signature_canonical(text)
    assert "HTTP 500" in canonical
    assert "HTTP 404" in canonical
    assert "after <NUM> retries" in canonical


def test_timestamp_and_windows_path_normalization():
    text = (
        r"2026-03-03T14:22:10.123+05:30 ERROR "
        r"at C:\Users\alice\airflow\dags\broken.py line 47"
    )
    canonical = create_signature_canonical(text)
    assert "<TS>" in canonical
    assert "<PATH>" in canonical
    assert "line <NUM>" in canonical


def test_signature_regex_escapes_literal_regex_chars():
    template_text = r"Error [worker-1] (code=17) path=/tmp/a+b.py"
    candidate_text = r"Error [worker-2] (code=99) path=/tmp/a+b.py"

    regex = create_signature_regex(create_signature_canonical(template_text))
    assert re.search(regex, candidate_text)
