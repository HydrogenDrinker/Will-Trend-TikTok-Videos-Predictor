import pandas as pd
import numpy as np
import joblib
import os
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier, XGBRegressor
from sklearn.metrics import roc_auc_score, mean_absolute_error

# --- CẤU HÌNH ---
SHARED_DIR = "/opt/airflow/models"
INPUT_PARQUET = os.path.join(SHARED_DIR, "processed_features.parquet")
MODEL_CLF_PATH = os.path.join(SHARED_DIR, "trend_classifier.pkl")
MODEL_REG_PATH = os.path.join(SHARED_DIR, "engagement_regressor.pkl")

def train():
    print(">>> [TRAIN] Đang load dữ liệu...")
    if not os.path.exists(INPUT_PARQUET):
        print(f"❌ Không tìm thấy file: {INPUT_PARQUET}")
        return

    df = pd.read_parquet(INPUT_PARQUET)
    print(f" -> Load được {len(df)} dòng.")

    features = ['stats_likes', 'stats_shareCount', 'stats_commentCount', 'create_time']
    X = df.select_dtypes(include=[np.number]).drop(columns=['is_trending'], errors='ignore')
    y_class = df['is_trending']
    y_reg = df['stats_likes']

    X_train, X_test, y_c_train, y_c_test, y_r_train, y_r_test = train_test_split(X, y_class, y_reg, test_size=0.2)

    # 1. Train Classifier
    print(" -> Training Classifier...")
    clf = XGBClassifier(n_estimators=50, use_label_encoder=False, eval_metric='logloss')
    clf.fit(X_train, y_c_train)
    
    # 2. Train Regressor
    print(" -> Training Regressor...")
    reg = XGBRegressor(n_estimators=50)
    reg.fit(X_train, y_r_train)

    # 3. Luu Model
    print(" -> Saving Models...")
    joblib.dump(clf, MODEL_CLF_PATH)
    joblib.dump(reg, MODEL_REG_PATH)
    
    print(f"✅ Hai model đã được lưu tại: {SHARED_DIR}")

if __name__ == "__main__":
    train()