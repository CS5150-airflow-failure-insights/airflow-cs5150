from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable, Connection
from airflow import settings

def validate_config():
    """Checks that required Airflow Variables exist."""
    required_vars = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_DATABASE"]
    for var in required_vars:
        Variable.get(var)  # raises KeyError if missing

def extract_from_api():
    """Simulates pulling data from an external API using a stored connection."""
    session = settings.Session()
    conn = session.query(Connection).filter(
        Connection.conn_id == "analytics_postgres"
    ).first()
    if conn is None:
        raise Exception(
            "The conn_id 'analytics_postgres' isn't defined. "
            "Please add it in Admin > Connections."
        )
    print("Connection found, extracting data...")

def transform_data():
    api_key = Variable.get("ANALYTICS_API_KEY")
    print(f"Transforming with key ending in ...{api_key[-4:]}")

def load_to_warehouse():
    account = Variable.get("SNOWFLAKE_ACCOUNT")
    print(f"Loading to Snowflake account: {account}")

with DAG(
    dag_id="data_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["demo", "data-team"],
) as dag:
    t1 = PythonOperator(task_id="validate_config",    python_callable=validate_config)
    t2 = PythonOperator(task_id="extract_from_api",   python_callable=extract_from_api)
    t3 = PythonOperator(task_id="transform_data",     python_callable=transform_data)
    t4 = PythonOperator(task_id="load_to_warehouse",  python_callable=load_to_warehouse)

    # t1 >> t2 >> t3 >> t4