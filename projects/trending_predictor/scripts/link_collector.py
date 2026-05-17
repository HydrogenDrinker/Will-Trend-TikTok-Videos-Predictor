import time
import random
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- CẤU HÌNH ---
TARGET_URL = "https://www.tiktok.com/tag/xuhuong" 
OUTPUT_LINK_FILE = "../../../data/21dec_video_links.txt"
TARGET_COUNT = 100

def collect_links():
    existing_links = set()
    if os.path.exists(OUTPUT_LINK_FILE):
        with open(OUTPUT_LINK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                clean_link = line.strip()
                if clean_link:
                    existing_links.add(clean_link)
    
    print(f"Đã có sẵn {len(existing_links)} link trong file {OUTPUT_LINK_FILE}.")
    print(f"Mục tiêu: Tìm thêm {TARGET_COUNT} link mới...")

    # Cấu hình Chrome
    chrome_options = Options()
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    print(">>> Đang khởi động trình duyệt...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    new_links = set() # Chỉ chứa các link mới tìm được trong phiên này

    try:
        driver.get(TARGET_URL)
        time.sleep(3)

        print("\n" + "="*50)
        print("BƯỚC ĐĂNG NHẬP")
        print("Hãy đăng nhập thủ công trên trình duyệt (nếu chưa đăng nhập).")
        input("Đăng nhập xong thì Bấm [ENTER] tại đây để chạy tiếp...")
        print("="*50 + "\n")
        
        no_new_data_count = 0
        
        print(f">>> Bắt đầu quét...")
        
        while len(new_links) < TARGET_COUNT:
            # Lấy link hiện tại trên màn hình
            elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/video/']")
            current_batch_new = 0
            
            for elem in elements:
                try:
                    href = elem.get_attribute('href')
                    # Link phải chưa có trong file CŨ và chưa có trong list MỚI
                    if href and (href not in existing_links) and (href not in new_links):
                        new_links.add(href)
                        current_batch_new += 1
                except: continue
            
            print(f"   -> Tìm thấy: {len(new_links)} link mới (Vừa thêm: {current_batch_new})...")
            
            if len(new_links) >= TARGET_COUNT:
                break

            # Kiểm tra kẹt
            if current_batch_new == 0:
                no_new_data_count += 1
                print(f"   Chưa thấy link mới... (Thử cuộn {no_new_data_count}/5)")
                
                # Mẹo kích hoạt load
                driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_UP)
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                if no_new_data_count >= 5:
                    print("Không tìm thấy link mới nào nữa. Dừng quét")
                    break
            else:
                no_new_data_count = 0 

            # Smart Scroll Logic
            body = driver.find_element(By.TAG_NAME, 'body')
            body.send_keys(Keys.END)
            time.sleep(random.uniform(1.5, 3.0)) 
            driver.execute_script("window.scrollBy(0, -300);")
            time.sleep(random.uniform(1.0, 2.0))
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2.0, 4.0))

    except Exception as e:
        print(f"Lỗi: {e}")
        
    finally:
        driver.quit()
        
    # Lưu file (Chế độ Append - 'a'; Nếu muốn viết đè luôn thì dùng 'w')
    if len(new_links) > 0:
        print(f"\n>>> Đang lưu thêm {len(new_links)} link mới vào cuối file...")
        # Mở file với mode 'a' (append) thay vì 'w' (write)
        with open(OUTPUT_LINK_FILE, "a", encoding="utf-8") as f:
            for link in new_links:
                f.write(link + "\n")
        print(f"Hoàn tất! Tổng cộng trong file giờ có {len(existing_links) + len(new_links)} link.")
    else:
        print("\nKhông tìm được link mới nào để lưu.")

if __name__ == "__main__":
    collect_links()