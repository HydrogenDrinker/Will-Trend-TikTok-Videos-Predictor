# base/Dockerfile
FROM apache/airflow:2.9.0-python3.10

USER root

# 1. Cài đặt Java (Bắt buộc để chạy Spark) và các thư viện hệ thống cho OpenCV
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    libgl1-mesa-glx \
    libglib2.0-0 \
    procps \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y ffmpeg

# Thiết lập biến môi trường JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV SPARK_HOME=/home/airflow/.local/lib/python3.10/site-packages/pyspark

USER airflow

# 2. Copy và cài đặt các thư viện Python (YOLO, PhoBERT, Spark...)
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# --- MỚI: Tải Spark-Kafka Jars ---
# Lý do: Để Spark Worker đọc được Kafka mà không cần download internet mỗi lần chạy job
# Phiên bản Jar phải khớp với phiên bản Spark (PySpark thường cài bản mới nhất, vd 3.5.0) và Scala 2.12
RUN curl -o $SPARK_HOME/jars/spark-sql-kafka-0-10_2.12-3.5.0.jar https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.0/spark-sql-kafka-0-10_2.12-3.5.0.jar && \
    curl -o $SPARK_HOME/jars/kafka-clients-3.5.1.jar https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.5.1/kafka-clients-3.5.1.jar && \
    curl -o $SPARK_HOME/jars/commons-pool2-2.11.1.jar https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar && \
    curl -o $SPARK_HOME/jars/spark-token-provider-kafka-0-10_2.12-3.5.0.jar https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.0/spark-token-provider-kafka-0-10_2.12-3.5.0.jar