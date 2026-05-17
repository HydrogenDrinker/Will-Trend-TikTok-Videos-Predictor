import json
import subprocess
import time
import os
from datetime import datetime
import feedparser
from pytrends.request import TrendReq

# --- CẤU HÌNH ---
INPUT_LINK_FILE = "save1.txt"
OUTPUT_DATA_FILE = "18dec_trending_data_for_spark.json"

# Hàm đọc file link
def load_links_from_file(filename):
    if not os.path.exists(filename):
        print(f"❌ Không tìm thấy file {filename}. Hãy chạy link_collector.py trước!")
        return []

    with open(filename, 'r', encoding='utf-8') as f:
        links = [line.strip() for line in f if line.strip()]

    print(f"📂 Đã nạp thành công {len(links)} link từ file.")
    return links

# --- CÁC CLASS CRAWLER ---
class ContextCrawler:
    def get_google_trends(self):
        print(">>> 1. Đang lấy Google Trends...")
        try:
            pytrends = TrendReq(hl='vi-VN', tz=420)
            trending = pytrends.trending_searches(pn='vietnam')
            return trending[0].tolist()[:10]
        except:
            return ["Trend A", "Trend B"] # Fallback

    def get_news_headlines(self):
        print(">>> 2. Đang lấy News Headlines...")
        headlines = []
        try:
            feed = feedparser.parse("https://vnexpress.net/rss/giai-tri.rss")
            headlines = [entry.title for entry in feed.entries[:5]]
            return headlines
        except:
            return []

class TikTokCrawler:
    def fetch_metadata(self, url):
        cmd = ['yt-dlp', '--dump-json', '--skip-download', '--no-warnings', url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            if result.returncode != 0: return None
            return json.loads(result.stdout)
        except: return None

# --- MAIN PROCESS ---
def main():
    # 1. Load Link từ file
    input_urls = load_links_from_file(INPUT_LINK_FILE)
    if not input_urls: return

    # 2. Khởi tạo Context
    context_tool = ContextCrawler()
    market_trends = context_tool.get_google_trends()
    news_headlines = context_tool.get_news_headlines()
    crawl_time = int(time.time())

    final_dataset = []
    crawler = TikTokCrawler()

    print(f"\n>>> BẮT ĐẦU CRAWL CHI TIẾT {len(input_urls)} VIDEO...")

    # 3. Loop qua từng link
    for i, url in enumerate(input_urls):
        print(f"[{i+1}/{len(input_urls)}] Đang xử lý: {url} ...")

        raw = crawler.fetch_metadata(url)
        if not raw:
            print("   -> ⚠️ Bỏ qua (Lỗi hoặc Video đã xóa)")
            continue

        # Mapping dữ liệu
        video_data = {
            "crawl_timestamp": crawl_time,
            "video_id": raw.get('id'),
            "video_url_mp4": raw.get('url'),
            "caption": raw.get('description') or raw.get('title', ''),
            "hashtags": raw.get('tags', []),
            "music_meta": {
                "music_id": raw.get('track_id') or raw.get('id'), # ID nhạc
                "music_title": raw.get('track', 'Original Sound'), # Tên bài hát
                "music_artist": raw.get('artist', 'Unknown'),      # Ca sĩ/Người tạo nhạc
                "music_album": raw.get('album', '')
            },

            # Context
            "context_trends": market_trends,
            "context_news": news_headlines,
            "upload_timestamp": raw.get('timestamp'),

            # Author & Stats
            "author_id": raw.get('uploader_id'),
            "author_name": raw.get('uploader'),
            "author_followers": raw.get('channel_follower_count', 0),
            "stats_likes": raw.get('like_count', 0),
            "stats_shares": raw.get('repost_count', 0),
            "stats_comments": raw.get('comment_count', 0)
        }

        final_dataset.append(video_data)

        # Auto-save checkpoint
        if len(final_dataset) % 10 == 0:
            print("   -> (Auto-save checkpoint...)")
            with open(OUTPUT_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(final_dataset, f, ensure_ascii=False, indent=4)

    # 4. Lưu lần cuối
    with open(OUTPUT_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_dataset, f, ensure_ascii=False, indent=4)

    print(f"\n🎉 HOÀN TẤT! Đã lưu {len(final_dataset)} dòng dữ liệu vào {OUTPUT_DATA_FILE}")

if __name__ == "__main__":
    main()