from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import logging

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 2, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def log_various_levels():
    """Function that logs at different levels for testing."""
    logger = logging.getLogger(__name__)
    
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    
    # Log some data processing
    logger.info("Processing 100 records")
    logger.info("Completed successfully")
    
    return "Task completed"

def task_with_error():
    """Function that demonstrates error logging."""
    logger = logging.getLogger(__name__)
    logger.error("Something went wrong!")
    logger.warning("This is a warning before exception")
    raise Exception("Random failure for testing")

with DAG(
    'test_logging_dag',
    default_args=default_args,
    description='A DAG for testing log viewing functionality',
    schedule=timedelta(days=1),
    catchup=False,
    tags=['test', 'logging'],
) as dag:

    start_task = BashOperator(
        task_id='start',
        bash_command='echo "Starting test DAG"',
    )

    log_task = PythonOperator(
        task_id='log_various_levels',
        python_callable=log_various_levels,
    )

    bash_log_task = BashOperator(
        task_id='bash_with_output',
        bash_command='echo "Bash task output"; sleep 2; echo "Processing complete"',
    )

    # This task will fail - useful for testing error logs
    error_task = PythonOperator(
        task_id='task_with_error',
        python_callable=task_with_error,
        trigger_rule='all_done',  # Run even if previous tasks fail
    )

    start_task >> log_task >> bash_log_task >> error_task