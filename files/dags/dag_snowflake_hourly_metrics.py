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
DAG: snowflake_hourly_metrics
Scenario: Missing Airflow Variable (Group 3 of 2)

Real-world context
------------------
A second DAG owned by a different team (Platform Engineering vs. Data
Engineering) that also reads from Snowflake. Both teams stored the Snowflake
credentials as Airflow Variables under the same key names, because that's the
pattern established at the company.

When a new developer clones the repo and runs `breeze start-airflow` for the
first time, ALL Snowflake DAGs fail within minutes of each other. The developer
sees multiple red DAGs all with "KeyError: SNOWFLAKE_ACCOUNT" and has no idea
if this is a code bug or an environment setup issue.

A shared error note from a teammate who survived this onboarding would say:
  "This is not a bug — you need to register 3 Airflow Variables before these
   DAGs will run. Go to Admin > Variables and add:
     SNOWFLAKE_ACCOUNT  = acme.us-east-1 (see #data-platform Slack)
     SNOWFLAKE_WAREHOUSE = COMPUTE_WH
     SNOWFLAKE_PASSWORD  = [in 1Password under 'Snowflake Prod ETL user']
   See also: https://wiki.acme.com/data/airflow-local-setup"

Similarity test target
-----------------------
Error signature is identical to `dag_snowflake_daily_load.py`.
The log context lines differ (hourly schedule, different query),
but the KeyError line is byte-for-byte the same — tests *exact* matching.
"""

from __future__ import annotations

import datetime
import logging

from airflow.sdk import DAG, task

log = logging.getLogger(__name__)


def _simulate_missing_variable_error():
    """Same missing-variable pattern as snowflake_daily_load."""
    log.info("Initializing Snowflake connector for hourly metrics push")
    log.info("Reading credentials from Airflow Variables: SNOWFLAKE_ACCOUNT, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_PASSWORD")
    log.info("Checking Variable: SNOWFLAKE_PASSWORD ... found")
    log.info("Checking Variable: SNOWFLAKE_WAREHOUSE ... found")
    log.info("Checking Variable: SNOWFLAKE_ACCOUNT ...")
    log.error(
        "KeyError: 'SNOWFLAKE_ACCOUNT'\n"
        "  File \".../airflow/models/variable.py\", line 176, in get\n"
        "    raise KeyError(key)\n"
        "KeyError: 'SNOWFLAKE_ACCOUNT'"
    )
    raise KeyError("SNOWFLAKE_ACCOUNT")


with DAG(
    dag_id="snowflake_hourly_metrics",
    description="Pushes real-time product metrics (DAU, sessions, errors) into Snowflake every hour.",
    schedule="@hourly",
    start_date=datetime.datetime(2025, 1, 1),
    catchup=False,
    tags=["snowflake", "metrics", "platform", "demo-error"],
) as dag:

    @task()
    def init_snowflake_connection():
        log.info("Starting hourly metrics task — run window: last 60 minutes")
        _simulate_missing_variable_error()

    @task()
    def fetch_product_metrics():
        log.info("Querying product event stream for: dau, sessions, p99_latency, error_rate")

    @task()
    def write_metrics_to_snowflake():
        log.info("INSERT INTO snowflake.hourly_metrics (metric, value, ts) VALUES (...)")

    @task()
    def alert_on_anomaly():
        log.info("Checking metric thresholds — alerting #platform-alerts if error_rate > 1%")

    init = init_snowflake_connection()
    fetch = fetch_product_metrics()
    write = write_metrics_to_snowflake()
    alert = alert_on_anomaly()

    init >> fetch >> write >> alert
