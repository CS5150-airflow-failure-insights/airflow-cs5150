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