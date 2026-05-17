import sys
import shutil
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType

# --- CẤU HÌNH ---
SHARED_DIR = "/opt/airflow/models" 
OUTPUT_PARQUET = os.path.join(SHARED_DIR, "processed_features.parquet")

def run_spark_kafka_job():
    print(">>> [SPARK] Khởi tạo Spark Session...")
    spark = SparkSession.builder \
        .appName("TrendPredictionKafka") \
        .master("spark://tv-spark-master:7077") \
        .config("spark.driver.memory", "2g") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    # Schema
    json_schema = StructType([
        StructField("id", StringType()),
        StructField("video_url", StringType()),
        StructField("author_unique_id", StringType()),
        StructField("desc", StringType()),
        StructField("create_time", LongType()),
        StructField("stats_diggCount", IntegerType()), # Like
        StructField("stats_shareCount", IntegerType()),
        StructField("stats_commentCount", IntegerType()),
        StructField("is_trending", IntegerType())
    ])

    print(">>> [SPARK] Đọc từ Kafka...")
    df_raw = spark.read \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "tv-kafka:9092") \
        .option("subscribe", "tiktok_raw_data") \
        .option("startingOffsets", "earliest") \
        .load()

    # Parse JSON
    df = df_raw.select(from_json(col("value").cast("string"), json_schema).alias("data")).select("data.*")
    df_processed = df.withColumnRenamed("desc", "caption") \
                     .withColumnRenamed("stats_diggCount", "stats_likes") \
                     .fillna(0)

    print(f">>> [SPARK] Lưu file Parquet xuống: {OUTPUT_PARQUET}")
    # Ghi đè file cũ
    df_processed.write.mode("overwrite").parquet(OUTPUT_PARQUET)
    
    print("✅ [SPARK] Xử lý xong!")
    spark.stop()

if __name__ == "__main__":
    run_spark_kafka_job()