#
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

"""
Add error signature and error note tables.

Revision ID: 6d58f39f2cb1
Revises: a1f4b3c9d2e8
Create Date: 2026-03-03 14:25:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6d58f39f2cb1"
down_revision = "a1f4b3c9d2e8"
branch_labels = None
depends_on = None
airflow_version = "3.2.0"


def upgrade():
    """Tables are created by the canonical error insight migration."""
    return None


def downgrade():
    """Tables are dropped by the canonical error insight migration."""
    return None
