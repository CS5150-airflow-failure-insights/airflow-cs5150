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

import hashlib
import re

UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
TIMESTAMP_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?)?\b"
)
PATH_PATTERN = re.compile(r"(?:(?:[A-Za-z]:\\)|/)[^\s:]+")
HTTP_STATUS_PATTERN = re.compile(r"\bHTTP\s+([1-5]\d{2})\b", flags=re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"\d+")

PLACEHOLDER_REGEX = {
    "<TS>": r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?)?",
    "<NUM>": r"\d+",
    "<PATH>": r"(?:(?:[A-Za-z]:\\)|/)[^\s:]+",
    "<UUID>": r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
}


def normalize_highlighted_text(highlighted_text: str) -> str:
    """Normalize whitespace and trim highlighted text."""
    return " ".join(highlighted_text.strip().split())


def create_signature_canonical(highlighted_text: str) -> str:
    """Create canonical signature by replacing run-specific values with placeholders."""
    canonical = normalize_highlighted_text(highlighted_text)
    canonical = UUID_PATTERN.sub("<UUID>", canonical)
    canonical = TIMESTAMP_PATTERN.sub("<TS>", canonical)
    canonical = PATH_PATTERN.sub("<PATH>", canonical)

    # Keep HTTP status codes stable while replacing other numeric values.
    protected_http_codes: dict[str, str] = {}

    def _protect_http_code(match: re.Match[str]) -> str:
        key = f"__HTTP_CODE_{'X' * (len(protected_http_codes) + 1)}__"
        protected_http_codes[key] = match.group(1)
        return f"HTTP {key}"

    canonical = HTTP_STATUS_PATTERN.sub(_protect_http_code, canonical)
    canonical = NUMBER_PATTERN.sub("<NUM>", canonical)
    for key, code in protected_http_codes.items():
        canonical = canonical.replace(key, code)
    return canonical


def create_signature_regex(signature_canonical: str) -> str:
    """Convert canonical signature with placeholders into a safe regex string."""
    regex = re.escape(signature_canonical)
    for placeholder, fragment in PLACEHOLDER_REGEX.items():
        regex = regex.replace(re.escape(placeholder), fragment)
    return regex


def create_signature_hash(signature_canonical: str) -> str:
    """Create deterministic hash for fast signature lookup."""
    return hashlib.sha256(signature_canonical.encode("utf-8")).hexdigest()
