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
DAG: snowflake_daily_load
Scenario: Missing Airflow Variable (Group 3 of 2)

Real-world context
------------------
"It works on my machine / in staging / why won't it work in prod?"

This is the #1 onboarding error for new Airflow deployments and the most
common failure when promoting DAGs from dev → staging → production. Engineers
store secrets and config in Airflow Variables or Connections, but those are
stored in the metadata DB — not in git. When a new environment is spun up
(or a teammate runs the project for the first time), the variables don't
exist yet.

Airflow raises a KeyError with a message that's technically accurate but
completely unhelpful to someone who has never set up the project before:
    KeyError: 'SNOWFLAKE_ACCOUNT'

The fix isn't in the code at all — you have to:
  1. Go to Airflow UI > Admin > Variables
  2. Add three specific variables with values from the password manager
  3. Know where those values are stored

A shared error note is *perfect* for this. The note says exactly which
variables to create and points to the internal wiki / 1Password entry.

Similarity test target
-----------------------
This DAG and `dag_snowflake_hourly_metrics.py` raise identical
KeyError: 'SNOWFLAKE_ACCOUNT' lines. The similarity matcher should treat
them as a match regardless of the surrounding context lines.
"""

from __future__ import annotations

import datetime
import logging

from airflow.sdk import DAG, task

log = logging.getLogger(__name__)

# These variable names are what your team would actually set in Airflow UI
_REQUIRED_VARIABLES = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_PASSWORD"]


def _simulate_missing_variable_error():
    """
    Mirrors the exact error Airflow raises when Variable.get() is called for
    a key that doesn't exist and no default is provided.

    Real Airflow log:
        INFO  - Reading config from Airflow Variables
        ERROR - KeyError: 'SNOWFLAKE_ACCOUNT'
        ERROR -   File ".../airflow/models/variable.py", line 176, in get
                    raise KeyError(key)
                  KeyError: 'SNOWFLAKE_ACCOUNT'
    """
    log.info("Reading Snowflake connection config from Airflow Variables")
    log.info("Required variables: %s", _REQUIRED_VARIABLES)
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
    dag_id="snowflake_daily_load",
    description="Loads processed event data from S3 staging into Snowflake data warehouse (daily batch).",
    schedule="@daily",
    start_date=datetime.datetime(2025, 1, 1),
    catchup=False,
    tags=["snowflake", "etl", "demo-error"],
) as dag:

    @task()
    def read_snowflake_config():
        log.info("Initializing Snowflake connector — reading credentials from Airflow Variables")
        _simulate_missing_variable_error()

    @task()
    def load_events_to_snowflake():
        log.info("COPY INTO snowflake.events FROM @s3_stage/events/2025-01-14/")

    @task()
    def run_dbt_models():
        log.info("Triggering downstream dbt models: stg_events, fct_daily_active_users")

    config = read_snowflake_config()
    load = load_events_to_snowflake()
    dbt = run_dbt_models()

    config >> load >> dbt
