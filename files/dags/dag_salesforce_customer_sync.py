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
DAG: salesforce_customer_sync
Scenario: API Rate Limit / HTTP 429 Error (Group 2 of 2)

Real-world context
------------------
This is one of the most frustrating "why is this randomly broken?" errors in
data engineering orgs. Multiple DAGs all call the Salesforce REST API and
are scheduled at the same time (e.g. 9:00 AM). Salesforce enforces an org-wide
API call limit (15,000/day for most editions, 25,000 for Enterprise).

When the combined call volume of all DAGs hits the cap, they all start
responding with HTTP 429. The error message says "Too Many Requests" but
doesn't tell you *which other DAG* is eating the quota.

The fix requires knowing:
  1. Salesforce limits are *org-wide*, not per-application
  2. You can check remaining quota via: GET /services/data/v56.0/limits/
  3. You need to stagger DAG schedules across the day
  4. Long-term: use Salesforce bulk API for large exports instead

An error note here saves every new data engineer hours of head-scratching.

Similarity test target
-----------------------
This DAG and `dag_salesforce_opportunity_sync.py` both raise
`requests.exceptions.HTTPError: 429 Too Many Requests`. Same error,
different endpoint, different team. Perfect similarity match test case.
"""

from __future__ import annotations

import datetime
import logging

from airflow.sdk import DAG, task

log = logging.getLogger(__name__)

_SALESFORCE_API_BASE = "https://yourorg.my.salesforce.com/services/data/v56.0"
_CUSTOMER_ENDPOINT = f"{_SALESFORCE_API_BASE}/query/?q=SELECT+Id,Name,Email+FROM+Contact+LIMIT+5000"


def _simulate_rate_limit_error(endpoint: str, records_fetched: int = 0):
    """
    Mirrors the real requests + Salesforce 429 traceback.

    Real log output:
        INFO - Fetching page 3 of contacts from Salesforce API
        INFO - GET https://yourorg.my.salesforce.com/services/data/v56.0/query/... [200]
        ERROR - GET https://yourorg.my.salesforce.com/services/data/v56.0/query/... [429]
        ERROR - requests.exceptions.HTTPError: 429 Client Error: Too Many Requests
                for url: https://yourorg.my.salesforce.com/services/data/v56.0/query/...
        ERROR - Response body: {"errorCode":"REQUEST_LIMIT_EXCEEDED",
                "message":"TotalRequests Limit exceeded."}
    """
    log.info("Authenticating with Salesforce OAuth2 (client_credentials flow)")
    log.info("Starting paginated fetch from: %s", endpoint)
    for page in range(1, 4):
        log.info("GET %s&page=%d [200] — fetched %d records", endpoint, page, records_fetched + page * 500)
    log.error("GET %s&page=4 [429]", endpoint)
    log.error(
        "requests.exceptions.HTTPError: 429 Client Error: Too Many Requests\n"
        "for url: %s&page=4\n"
        'Response: {"errorCode":"REQUEST_LIMIT_EXCEEDED",'
        '"message":"TotalRequests Limit exceeded."}',
        endpoint,
    )
    raise Exception(
        "requests.exceptions.HTTPError: 429 Client Error: Too Many Requests\n"
        f"for url: {endpoint}&page=4\n"
        'Response body: {"errorCode":"REQUEST_LIMIT_EXCEEDED",'
        '"message":"TotalRequests Limit exceeded."}'
    )


with DAG(
    dag_id="salesforce_customer_sync",
    description="Syncs Salesforce Contact records into the internal CRM database.",
    schedule="0 9 * * 1-5",  # 9am weekdays — same time as opportunity_sync!
    start_date=datetime.datetime(2025, 1, 1),
    catchup=False,
    tags=["salesforce", "crm", "demo-error"],
) as dag:

    @task()
    def fetch_contacts_from_salesforce():
        log.info("Fetching all active Contact records from Salesforce")
        _simulate_rate_limit_error(endpoint=_CUSTOMER_ENDPOINT, records_fetched=1500)

    @task()
    def upsert_contacts_to_crm():
        log.info("Upserting Contact records into internal CRM table: crm.contacts")

    @task()
    def update_sync_checkpoint():
        log.info("Writing last_synced_at checkpoint to airflow Variable: sf_contact_last_sync")

    fetch = fetch_contacts_from_salesforce()
    upsert = upsert_contacts_to_crm()
    checkpoint = update_sync_checkpoint()

    fetch >> upsert >> checkpoint
