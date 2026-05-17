import json
import re
import cv2
import pandas as pd
import numpy as np
import torch
from datetime import datetime
from ultralytics import YOLO
from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification

FILE_TRENDING = "../../../data/data_xuhuong.json"
FILE_EXPLORE  = "../../../data/data_explore.json"
OUTPUT_FILE   = "training_data_final_merged.parquet"   
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"🚀 Đang chạy trên thiết bị: {DEVICE}")

# ==============================================================================
# MODULE 1: DATA CLEANER
# ==============================================================================
class DataCleaner:
    def process(self, df):
        print("\n>>> [1/3] Đang làm sạch dữ liệu...")
        df['upload_dt'] = pd.to_datetime(df['upload_timestamp'], unit='s')
        df['crawl_dt'] = pd.to_datetime(df['crawl_timestamp'], unit='s')
        df['F7_lifespan_hours'] = (df['crawl_timestamp'] - df['upload_timestamp']) / 3600
        
        def get_tags(row):
            if isinstance(row['hashtags'], list) and len(row['hashtags']) > 0: 
                return row['hashtags']
            return re.findall(r"#(\w+)", str(row['caption']))

        df['hashtags'] = df.apply(get_tags, axis=1)
        # Handle trường hợp hashtags bị None
        df['hashtags'] = df['hashtags'].apply(lambda x: x if isinstance(x, list) else [])
        
        df['F8_hashtag_count'] = df['hashtags'].apply(len)
        
        trend_keywords = ['xuhuong', 'trend', 'fyp', 'viral', 'thinhhanh']
        df['F8_is_trend_tag'] = df['hashtags'].apply(lambda tags: 1 if any(t.lower() in trend_keywords for t in tags) else 0)
        df['author_followers'] = df['author_followers'].fillna(0).astype(int)
        return df

# ==============================================================================
# MODULE 2: VISUAL PROCESSOR (YOLO + OPENCV FACE DETECT)
# ==============================================================================
class VisualProcessor:
    def __init__(self):
        print("\n>>> [2/3] Đang khởi tạo Visual Models...")
        self.yolo = YOLO("../../../models/yolov8n.pt") # Kiểm tra lại đường dẫn model
        
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        if self.face_cascade.empty():
            print("⚠️ Cảnh báo: Không load được Face Cascade. Tính năng Face Ratio sẽ = 0.")

    def extract_features(self, video_url):
        feats = {
            "F1_is_person": 0, "F1_is_product": 0, 
            "F2_face_ratio": 0.0, "F3_is_closeup": 0, "F_is_ad_visual": 0
        }
        
        try:
            cap = cv2.VideoCapture(video_url, cv2.CAP_FFMPEG)
            if not cap.isOpened(): return feats
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, 30) 
            ret, frame = cap.read()
            cap.release()
            if not ret: return feats
            
            h, w, _ = frame.shape

            # --- A. YOLO Logic ---
            results = self.yolo(frame, verbose=False)
            classes = [int(box.cls) for r in results for box in r.boxes]
            
            if 0 in classes: feats["F1_is_person"] = 1 
            product_ids = [39, 41, 67, 73, 44] 
            if any(c in product_ids for c in classes):
                feats["F1_is_product"] = 1
                feats["F_is_ad_visual"] = 1

            # --- B. OpenCV Logic ---
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            
            if len(faces) > 0:
                max_area = 0
                for (fx, fy, fw, fh) in faces:
                    area = fw * fh
                    if area > max_area: max_area = area
                
                ratio = max_area / (w * h)
                feats["F2_face_ratio"] = round(ratio, 4)
                if ratio > 0.10: feats["F3_is_closeup"] = 1

        except Exception:
            pass
            
        return feats
    
# ==============================================================================
# MODULE 3: TEXT PROCESSOR
# ==============================================================================
class TextProcessor:
    def __init__(self):
        print("\n>>> [3/3] Đang khởi tạo NLP Models (PhoBERT)...")
        self.tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
        self.embed_model = AutoModel.from_pretrained("vinai/phobert-base").to(DEVICE)
        self.sent_tokenizer = AutoTokenizer.from_pretrained("wonrax/phobert-base-vietnamese-sentiment")
        self.sent_model = AutoModelForSequenceClassification.from_pretrained("wonrax/phobert-base-vietnamese-sentiment").to(DEVICE)
        self.ad_keywords = ['mua', 'giá', 'shop', 'link', 'đặt hàng', 'ib', 'sale', 'freeship']

    def get_embedding(self, text):
        if not text: return np.zeros(768).tolist()
        # Truncate text quá dài để tránh lỗi model
        text = str(text)[:256] 
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=128, padding=True).to(DEVICE)
        with torch.no_grad():
            out = self.embed_model(**inputs)
        return out.last_hidden_state.mean(dim=1).cpu().numpy()[0].tolist()

    def get_sentiment(self, text):
        if not text: return 0
        text = str(text)[:256]
        inputs = self.sent_tokenizer(text, return_tensors="pt", truncation=True, max_length=128).to(DEVICE)
        with torch.no_grad():
            out = self.sent_model(**inputs)
        probs = torch.nn.functional.softmax(out.logits, dim=-1)
        pred = torch.argmax(probs).item()
        mapping = {0: -1, 1: 1, 2: 0}
        return mapping.get(pred, 0)

    def check_ad_text(self, text):
        return 1 if any(k in str(text).lower() for k in self.ad_keywords) else 0

# ==============================================================================
# MAIN
# ==============================================================================
def run_pipeline():
    # --- BƯỚC 0: LOAD VÀ GỘP DATA ---
    print(">>> [0/3] Đang tải và gộp dữ liệu...")
    try:
        # 1. Load data Trending (Label = 1)
        with open(FILE_TRENDING, 'r', encoding='utf-8') as f:
            data_trend = json.load(f)
        df_trend = pd.DataFrame(data_trend)
        df_trend['is_trending'] = 1  # <--- GÁN NHÃN 1
        print(f"   - Tìm thấy {len(df_trend)} video Xu Hướng.")

        # 2. Load data Explore (Label = 0)
        with open(FILE_EXPLORE, 'r', encoding='utf-8') as f:
            data_explore = json.load(f)
        df_explore = pd.DataFrame(data_explore)
        df_explore['is_trending'] = 0  # <--- GÁN NHÃN 0
        print(f"   - Tìm thấy {len(df_explore)} video Explore.")
        
        # 3. Gộp lại
        df = pd.concat([df_trend, df_explore], ignore_index=True)
        
        # 4. Xử lý trùng lặp (QUAN TRỌNG)
        # Nếu video xuất hiện ở cả 2 file, ta ưu tiên giữ dòng có nhãn 1 (Trend)
        # Cách làm: Sắp xếp theo is_trending giảm dần (1 trước, 0 sau), sau đó drop duplicate giữ dòng đầu
        df = df.sort_values(by='is_trending', ascending=False)
        df = df.drop_duplicates(subset=['video_id'], keep='first')
        
        print(f"   -> Tổng cộng sau khi gộp và lọc trùng: {len(df)} dòng.")
        print(f"      (Trend: {len(df[df['is_trending']==1])}, Non-Trend: {len(df[df['is_trending']==0])})")

    except FileNotFoundError as e:
        print(f"❌ Lỗi file: {e}")
        print("Vui lòng kiểm tra lại đường dẫn FILE_TRENDING và FILE_EXPLORE ở đầu file.")
        return

    # --- BƯỚC 1: CLEANING ---
    cleaner = DataCleaner()
    df = cleaner.process(df)

    # --- BƯỚC 2: VISUAL PROCESSING ---
    vis_proc = VisualProcessor()
    print("   -> Đang xử lý Video (YOLO + OpenCV)...")
    visual_features = []
    
    total_vids = len(df)
    for i, url in enumerate(df['video_url_mp4']):
        if (i+1) % 10 == 0: print(f"      Processing video {i+1}/{total_vids}...")
        visual_features.append(vis_proc.extract_features(url))
    
    # Gộp features vào DF chính
    df = df.reset_index(drop=True)
    df_vis = pd.DataFrame(visual_features)
    df = pd.concat([df, df_vis], axis=1)

    # --- BƯỚC 3: TEXT PROCESSING ---
    txt_proc = TextProcessor()
    print("   -> Đang xử lý Text (PhoBERT)...")
    
    # Xử lý Text Embedding
    df['F4_text_embedding'] = df['caption'].apply(txt_proc.get_embedding)
    df['F5_sentiment_score'] = df['caption'].apply(txt_proc.get_sentiment)
    df['is_text_ad'] = df['caption'].apply(txt_proc.check_ad_text)
    
    # Feature kết hợp
    df['F_is_ad_final'] = df.apply(lambda row: 1 if (row.get('F_is_ad_visual', 0) == 1 or row.get('is_text_ad', 0) == 1) else 0, axis=1)

    # --- BƯỚC 4: CLEANUP & SAVE ---
    final_df = df
    
    final_df.to_parquet(OUTPUT_FILE, index=False)
    print(f"\n✅ PIPELINE HOÀN TẤT! File Output: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_pipeline()