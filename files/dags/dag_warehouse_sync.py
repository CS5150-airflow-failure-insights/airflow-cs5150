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
DAG: warehouse_daily_sync
Scenario: Database Credentials / Connection Error (Group 1 of 2)

Real-world context
------------------
This is a very common org-level failure. A team runs multiple ETL pipelines that
all connect to a central analytics Postgres database. The database password rotates
every 90 days (enforced by the security team). When it rotates, every single DAG
that touches the DB starts failing with "FATAL: password authentication failed".

The fix is non-obvious from the error alone:
  - You have to know *which* Airflow Connection to update (postgres_analytics)
  - You have to know *where* the new password lives (e.g. 1Password, Vault, AWS Secrets)
  - You have to know the rotation schedule

This is EXACTLY the kind of tribal knowledge a shared error note captures.
A teammate who solved it last quarter can leave a note so the next person
doesn't spend 2 hours debugging.

Similarity test target
-----------------------
This DAG and `dag_analytics_export.py` both raise the same
psycopg2.OperationalError. Pasting either error into the note anchoring UI
should match the other DAG's error log.
"""

from __future__ import annotations

import datetime
import logging

from airflow.sdk import DAG, task

log = logging.getLogger(__name__)


def _simulate_db_connection_error():
    """
    Raises an exception that mirrors the real psycopg2 traceback you would see
    when an Airflow Connection's password is stale after a credential rotation.

    Real log output looks like:
        sqlalchemy.exc.OperationalError: (psycopg2.OperationalError)
        FATAL:  password authentication failed for user "analytics_user"
        (Background on this error at: https://sqlalche.me/e/14/e3q8)
    """
    log.info("Connecting to postgres_analytics (host=analytics-db.internal, port=5432, db=warehouse)")
    log.info("Executing: SELECT COUNT(*) FROM orders WHERE synced_at IS NULL")
    log.error(
        "sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) "
        "FATAL:  password authentication failed for user \"analytics_user\"\n"
        "(Background on this error at: https://sqlalche.me/e/14/e3q8)"
    )
    raise Exception(
        "sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) "
        "FATAL:  password authentication failed for user \"analytics_user\"\n"
        "(Background on this error at: https://sqlalche.me/e/14/e3q8)"
    )


with DAG(
    dag_id="warehouse_daily_sync",
    description="Syncs unprocessed orders from transactional DB into the analytics warehouse.",
    schedule="@daily",
    start_date=datetime.datetime(2025, 1, 1),
    catchup=False,
    tags=["etl", "warehouse", "demo-error"],
) as dag:

    @task()
    def extract_new_orders():
        log.info("Starting extract_new_orders task")
        log.info("Reading from source: orders table, last_sync_ts=2025-01-14T08:00:00Z")
        _simulate_db_connection_error()

    @task()
    def transform_order_records():
        # This task never runs because extract fails, but it shows the full pipeline intent
        log.info("Transforming raw order records to warehouse schema")

    @task()
    def load_to_warehouse():
        log.info("Loading transformed records into warehouse.orders_fact table")

    extract = extract_new_orders()
    transform = transform_order_records()
    load = load_to_warehouse()

    extract >> transform >> load
