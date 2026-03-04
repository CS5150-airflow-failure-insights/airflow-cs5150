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
DAG: salesforce_opportunity_sync
Scenario: API Rate Limit / HTTP 429 Error (Group 2 of 2)

Real-world context
------------------
Owned by the Revenue Ops team (different from the CRM team that owns
salesforce_customer_sync). Both DAGs are scheduled at 9am. They share the
same Salesforce org and the same API quota pool. When one DAG's quota pushes
the org over the daily limit, the other DAG starts failing with 429 — even
though it individually would have been fine.

Neither team knows about the other's schedule. This is the *exact* scenario
where a shared error note stops two teams from both filing the same support
ticket. The note created on salesforce_customer_sync should appear as a
"Potential Match" when someone views this DAG's failing log.

Similarity test target
-----------------------
Error signature is ~92% identical to `dag_salesforce_customer_sync.py`.
The endpoint URL and record counts differ; the core 429 error line is the same.
"""

from __future__ import annotations

import datetime
import logging

from airflow.sdk import DAG, task

log = logging.getLogger(__name__)

_SALESFORCE_API_BASE = "https://yourorg.my.salesforce.com/services/data/v56.0"
_OPPORTUNITY_ENDPOINT = (
    f"{_SALESFORCE_API_BASE}/query/?q=SELECT+Id,Name,Amount,StageName+FROM+Opportunity+LIMIT+10000"
)


def _simulate_rate_limit_error(endpoint: str):
    """
    Same 429 error flavour as salesforce_customer_sync, different endpoint/context.
    """
    log.info("Authenticating with Salesforce OAuth2 (client_credentials flow)")
    log.info("Fetching Opportunity pipeline data for weekly revenue forecast")
    for page in range(1, 6):
        log.info("GET %s&page=%d [200] — fetched %d records", endpoint, page, page * 2000)
    log.error("GET %s&page=6 [429]", endpoint)
    log.error(
        "requests.exceptions.HTTPError: 429 Client Error: Too Many Requests\n"
        "for url: %s&page=6\n"
        'Response: {"errorCode":"REQUEST_LIMIT_EXCEEDED",'
        '"message":"TotalRequests Limit exceeded."}',
        endpoint,
    )
    raise Exception(
        "requests.exceptions.HTTPError: 429 Client Error: Too Many Requests\n"
        f"for url: {endpoint}&page=6\n"
        'Response body: {"errorCode":"REQUEST_LIMIT_EXCEEDED",'
        '"message":"TotalRequests Limit exceeded."}'
    )


with DAG(
    dag_id="salesforce_opportunity_sync",
    description="Syncs Salesforce Opportunity pipeline data for the weekly revenue forecast.",
    schedule="0 9 * * 1-5",  # 9am weekdays — competes with salesforce_customer_sync
    start_date=datetime.datetime(2025, 1, 1),
    catchup=False,
    tags=["salesforce", "revenue-ops", "demo-error"],
) as dag:

    @task()
    def fetch_opportunities():
        log.info("Starting Opportunity record fetch from Salesforce")
        _simulate_rate_limit_error(endpoint=_OPPORTUNITY_ENDPOINT)

    @task()
    def compute_pipeline_forecast():
        log.info("Aggregating opportunity amounts by stage for weekly forecast model")

    @task()
    def write_forecast_to_gsheet():
        log.info("Writing forecast output to Google Sheet: Revenue Ops > Weekly Pipeline")

    fetch = fetch_opportunities()
    forecast = compute_pipeline_forecast()
    gsheet = write_forecast_to_gsheet()

    fetch >> forecast >> gsheet
