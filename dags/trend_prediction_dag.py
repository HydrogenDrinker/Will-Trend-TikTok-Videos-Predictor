import sys
import os
import subprocess
from datetime import timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

# --- CONFIGURATION ---
PROJECT_DIR = "/opt/airflow/projects/trending_predictor"
SCRIPTS_DIR = f"{PROJECT_DIR}/scripts"

# Add scripts to path so we can import them directly
sys.path.append(SCRIPTS_DIR)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    'tiktok_streaming_lifecycle',
    default_args=default_args,
    description='Orchestrate Kafka Producer & Spark Consumer with Auto-Retrain',
    schedule_interval=timedelta(minutes=10), # Run this cycle every 10 minutes
    start_date=days_ago(1),
    catchup=False,
    tags=["tiktok", "streaming", "kafka", "spark"],
) as dag:

    # =================================================================
    # 1. SETUP & CHECK
    # =================================================================
    def check_environment():
        """Ensure paths and model folders exist before starting"""
        if not os.path.exists(f"{PROJECT_DIR}/raw_data"):
             raise FileNotFoundError("Raw Data folder not found. Mount volumes correctly.")
        print("✅ Environment Checked. Ready to stream.")

    t0_setup = PythonOperator(
        task_id='setup_environment',
        python_callable=check_environment
    )

    # =================================================================
    # 2. RUN PRODUCER (Python Operator)
    # =================================================================
    def run_kafka_producer_logic():
        """
        Imports and runs the Producer code directly.
        This reads the JSON file and pushes to Kafka.
        """
        try:
            # Import dynamically to ensure latest code is used
            import kafka_producer
            print("🚀 Starting Kafka Producer...")
            kafka_producer.send_data_to_kafka()
            print("✅ Kafka Producer finished sending batch.")
        except Exception as e:
            print(f"❌ Producer Failed: {e}")
            raise e

    t1_producer = PythonOperator(
        task_id='run_kafka_producer',
        python_callable=run_kafka_producer_logic,
        execution_timeout=timedelta(minutes=5)
    )

    # =================================================================
    # 3. RUN SPARK CONSUMER (Bash with Timeout)
    # =================================================================
    # We use BashOperator because we need to run 'spark-submit'.
    # We use 'timeout 3m' to let it run for 3 mins then stop it so the DAG continues.
    # The '|| true' ensures Airflow treats the timeout as a Success, not a Failure.
    
    spark_cmd = f"""
    timeout 3m /opt/airflow/projects/trending_predictor/scripts/spark_processor.py \
    || true
    """
    
    # NOTE: Since we are running spark-submit inside the Airflow worker container,
    # we usually need to call the spark binary. 
    # If your spark_processor.py uses 'SparkSession.builder...getOrCreate()',
    # you can actually run it with python directly provided libraries are installed.
    # Below assumes running via Python directly for simplicity in this setup:
    
    t2_consumer = BashOperator(
        task_id='run_spark_consumer',
        bash_command=f'timeout 3m python {SCRIPTS_DIR}/spark_processor.py || true',
        execution_timeout=timedelta(minutes=5)
    )

    # =================================================================
    # 4. AUTO RETRAIN MODEL (Python Operator)
    # =================================================================
    def run_retrain_logic():
        """Check if we have new data in Parquet and Retrain"""
        import train_model
        import os
        
        parquet_file = "/opt/airflow/models/processed_features.parquet"
        if os.path.exists(parquet_file):
            print("🔄 Found processed data. Starting Retraining...")
            train_model.train()
        else:
            print("⚠️ No Parquet file found. Skipping training.")

    t3_retrain = PythonOperator(
        task_id='auto_retrain_model',
        python_callable=run_retrain_logic,
        trigger_rule="all_done" # Run even if Consumer times out (which is expected)
    )

    # =================================================================
    # 5. INFERENCE & SAVE (Python Operator)
    # =================================================================
    def run_inference_logic():
        """Push results to Mongo"""
        from inference_to_mongo import save_predictions
        save_predictions()

    t4_save_mongo = PythonOperator(
        task_id='save_predictions',
        python_callable=run_inference_logic,
        trigger_rule="all_done"
    )

    # =================================================================
    # DAG ORCHESTRATION
    # =================================================================
    
    # 1. Check Env
    # 2. Run Producer AND Consumer in Parallel 
    #    (Producer feeds Kafka, Consumer reads Kafka simultaneously)
    # 3. Once Consumer time window ends, Train Model
    # 4. Save to Mongo
    
    t0_setup >> [t1_producer, t2_consumer] >> t3_retrain >> t4_save_mongo