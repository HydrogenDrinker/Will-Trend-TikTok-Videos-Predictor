import json
import os
import glob
import pandas as pd
from datetime import datetime

# --- CẤU HÌNH ĐƯỜNG DẪN ---
BASE_DIR = r"D:\Code\VideosToTrendPredictor\raw_data"
EXPLORE_DIR = os.path.join(BASE_DIR, "explore")
TRENDING_DIR = os.path.join(BASE_DIR, "trending")
OUTPUT_FILE = os.path.join(BASE_DIR, "final_merged_data.json")

def load_json_files(directory, label):
    """Đọc tất cả file .json trong thư mục và gán nhãn"""
    all_data = []
    files = glob.glob(os.path.join(directory, "*.json"))
    print(f"📂 Tìm thấy {len(files)} file trong {directory}")
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data = [data]
                
                for item in data:
                    item['is_trending'] = label
                    item['source_file'] = os.path.basename(file_path)
                    all_data.append(item)
        except Exception as e:
            print(f"❌ Lỗi đọc file {file_path}: {e}")
            
    return all_data

def main():
    print("🚀 Bắt đầu gộp dữ liệu...")

    # 1. Load dữ liệu
    explore_data = load_json_files(EXPLORE_DIR, label=0)
    trending_data = load_json_files(TRENDING_DIR, label=1)
    
    total_raw = len(explore_data) + len(trending_data)
    print(f"📊 Tổng số video thô: {total_raw} (Explore: {len(explore_data)}, Trending: {len(trending_data)})")

    if total_raw == 0:
        print("⚠️ Không có dữ liệu nào để xử lý. Kiểm tra lại đường dẫn folder!")
        return

    # 2. Chuyển sang DataFrame để xử lý trùng lặp dễ dàng
    df = pd.DataFrame(explore_data + trending_data)

    # 3. Tính toán các trường phụ trợ quan trọng
    # Tính tuổi video (giờ) tại thời điểm cào
    # Công thức: (Thời điểm cào - Thời điểm đăng) / 3600
    df['video_age_hours'] = (df['crawl_timestamp'] - df['upload_timestamp']) / 3600
    
    # Lọc rác: Bỏ các video lỗi có tuổi âm hoặc không có ID
    df = df[df['video_age_hours'] >= 0]
    df = df.dropna(subset=['video_id'])

    # 4. Xử lý Trùng lặp (Quan trọng nhất)
    # Logic: 
    # - Một video có thể xuất hiện nhiều ngày -> Lấy dữ liệu mới nhất (max crawl_timestamp)
    # - Một video có thể vừa ở Explore vừa ở Trending -> Ưu tiên nhãn Trending (max is_trending)
    
    print("... Đang xử lý trùng lặp và gộp nhãn ...")
    
    # Group theo video_id
    df_final = df.sort_values('crawl_timestamp', ascending=False).groupby('video_id', as_index=False).agg({
        'video_url_mp4': 'first',      # Lấy URL mới nhất
        'caption': 'first',
        'hashtags': 'first',
        'music_meta': 'first',
        'context_trends': 'first',
        'context_news': 'first',
        'upload_timestamp': 'first',
        'author_id': 'first',
        'author_followers': 'max',     # Lấy lượng follow cao nhất ghi nhận được
        'stats_likes': 'max',          # Lấy tương tác cao nhất (thường là mới nhất)
        'stats_shares': 'max',
        'stats_comments': 'max',
        'is_trending': 'max',          # Nếu từng là 1 (Trending) thì giữ là 1
        'crawl_timestamp': 'max',
        'video_age_hours': 'max'       # Lấy tuổi lớn nhất (tương ứng lúc cào mới nhất)
    })

    # 5. Xuất file
    print(f"✅ Đã xử lý xong. Còn lại {len(df_final)} video unique.")
    
    result_json = df_final.to_dict(orient='records')
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result_json, f, ensure_ascii=False, indent=4)
        
    print(f"💾 File đã được lưu tại: {OUTPUT_FILE}")
    print("👉 Bây giờ bạn hãy sửa kafka_producer.py để chỉ đọc file này!")

if __name__ == "__main__":
    main()