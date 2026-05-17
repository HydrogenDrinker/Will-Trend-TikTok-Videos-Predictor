import json
import os
import time
from kafka import KafkaProducer

# --- CẤU HÌNH ---
KAFKA_TOPIC = 'tiktok_raw_data'
KAFKA_BOOTSTRAP_SERVERS = 'tv-kafka:9092' 
DATA_FILE = '/opt/airflow/projects/trending_predictor/raw_data/final_merged_data.json'

def send_data_to_kafka():
    print(f">>> [PRODUCER] Kết nối tới Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    time.sleep(5) 
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
            max_request_size=5048576
        )
    except Exception as e:
        print(f"❌ Lỗi kết nối Kafka: {e}")
        return

    if not os.path.exists(DATA_FILE):
        print(f"❌ Không tìm thấy file dữ liệu: {DATA_FILE}")
        print("   Hãy chắc chắn bạn đã chạy merge_data.py và mount folder raw_data vào Docker.")
        return

    print(f"--- Đang đọc file {DATA_FILE}...")
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        videos = json.load(f)
    
    print(f"--- Bắt đầu đẩy {len(videos)} video vào Kafka...")
    
    for i, video in enumerate(videos):
        producer.send(KAFKA_TOPIC, value=video)
        
        if (i+1) % 100 == 0:
            print(f"   -> Đã gửi {i+1} video...")
            
    producer.flush()
    producer.close()
    print("✅ [PRODUCER] Hoàn tất!")

if __name__ == "__main__":
    send_data_to_kafka()