import pandas as pd
import numpy as np
import pymongo
import joblib
import os
from datetime import datetime

# --- CẤU HÌNH ---
MONGO_URI = "mongodb://tv-mongo:27017/"
DB_NAME = "tiktok_trends"
COLLECTION_NAME = "predictions"

SHARED_DIR = "/opt/airflow/models"
INPUT_PARQUET = os.path.join(SHARED_DIR, "processed_features.parquet")
MODEL_CLF_PATH = os.path.join(SHARED_DIR, "trend_classifier.pkl")
MODEL_REG_PATH = os.path.join(SHARED_DIR, "engagement_regressor.pkl")

def save_predictions():
    print(">>> [INFERENCE] Bắt đầu...")
    
    # 1. Load Data & Model
    if not os.path.exists(INPUT_PARQUET) or not os.path.exists(MODEL_CLF_PATH):
        print("❌ Thiếu file data hoặc file model!")
        return

    df = pd.read_parquet(INPUT_PARQUET)
    clf_model = joblib.load(MODEL_CLF_PATH)
    reg_model = joblib.load(MODEL_REG_PATH)

    # 2. Prepare
    X = df.select_dtypes(include=[np.number]).drop(columns=['is_trending'], errors='ignore')

    # 3. Predict
    print(" -> Predicting...")
    df['pred_is_trending'] = clf_model.predict(X)
    df['pred_trend_prob'] = clf_model.predict_proba(X)[:, 1]
    df['pred_likes'] = reg_model.predict(X)
    df['processed_at'] = datetime.now()

    # 4. Save to Mongo
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COLLECTION_NAME]

    records = df.to_dict('records')
    if records:
        # col.delete_many({}) 
        col.insert_many(records)
        print(f"✅ Đã lưu {len(records)} kết quả vào MongoDB.")
    
    client.close()

if __name__ == "__main__":
    save_predictions()