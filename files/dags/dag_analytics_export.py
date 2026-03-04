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
DAG: analytics_weekly_export
Scenario: Database Credentials / Connection Error (Group 1 of 2)

Real-world context
------------------
Same credential-rotation failure as warehouse_daily_sync, but this DAG is
owned by the Analytics team. It exports aggregated metrics for the BI dashboard.
When the password rotates BOTH DAGs break at the same time, but they are owned
by different teams. The fix is identical: update the `postgres_analytics`
Airflow Connection.

Similarity test target
-----------------------
The error signature in this DAG is intentionally ~95% identical to
`dag_warehouse_sync.py`. Selecting the traceback line in one log view should
surface the existing error note created on the other DAG as a "Potential Match".
"""

from __future__ import annotations

import datetime
import logging
import uuid

from airflow.sdk import DAG, task

log = logging.getLogger(__name__)

# Simulate a unique execution context (different run_id, different query)
_RUN_UUID = str(uuid.uuid4())[:8]


def _simulate_db_connection_error():
    """
    Same underlying psycopg2 error as warehouse_daily_sync, but the query and
    surrounding log lines differ slightly — perfect for testing 90%+ similarity
    matching rather than exact matching.
    """
    log.info("Connecting to postgres_analytics (host=analytics-db.internal, port=5432, db=metrics)")
    log.info("Executing: SELECT metric_name, SUM(value) FROM daily_metrics WHERE date='2025-01-14' GROUP BY 1")
    log.info("run_id=analytics_weekly_export__2025-01-14_%s", _RUN_UUID)
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
    dag_id="analytics_weekly_export",
    description="Aggregates weekly KPI metrics and exports them to the BI dashboard database.",
    schedule="@weekly",
    start_date=datetime.datetime(2025, 1, 1),
    catchup=False,
    tags=["analytics", "bi", "demo-error"],
) as dag:

    @task()
    def compute_weekly_kpis():
        log.info("Starting KPI aggregation for week ending 2025-01-14")
        _simulate_db_connection_error()

    @task()
    def format_dashboard_payload():
        log.info("Formatting KPI data as JSON for dashboard API")

    @task()
    def push_to_dashboard():
        log.info("POSTing metrics to internal BI dashboard: https://bi.internal/api/ingest")

    compute = compute_weekly_kpis()
    fmt = format_dashboard_payload()
    push = push_to_dashboard()

    compute >> fmt >> push
