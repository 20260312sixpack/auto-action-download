import os
import json
import time
import glob
from urllib.parse import quote
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- 環境変数 ---
USER_ID = os.environ["USER_ID"]
PASSWORD = os.environ["USER_PASS"]
json_creds = json.loads(os.environ["GCP_JSON"])

# --- 設定 ---
TARGET_URL = "https://asp1.six-pack.xyz/admin/report/ad/list"
DRIVE_FOLDER_ID = "1rygU940nK8eKoZX2emKv_HftRRjY87BW"

def upload_to_drive(file_path):
    """Google DriveにCSVファイルをアップロードする関数"""
    print(f"ドライブへのアップロードを開始: {file_path}")
    
    scopes = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(json_creds, scopes=scopes)
    service = build('drive', 'v3', credentials=creds)

    file_name = os.path.basename(file_path)
    
    file_metadata = {
        'name': file_name,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype='text/csv')

    file = service.files().create(
        body=file_metadata, 
        media_body=media, 
        fields='id', 
        supportsAllDrives=True
    ).execute()
    
    print(f"アップロード完了 File ID: {file.get('id')}")

def main():
    print("=== Ad Report CSV取得処理開始 ===")
    
    download_dir = os.path.join(os.getcwd(), "downloads_report")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 20)

    try:
        # --- 1. ログイン ---
        safe_user = quote(USER_ID, safe='')
        safe_pass = quote(PASSWORD, safe='')
        url_body = TARGET_URL.replace("https://", "").replace("http://", "")
        auth_url = f"https://{safe_user}:{safe_pass}@{url_body}"
        
        print(f"アクセス中: {TARGET_URL}")
        driver.get(auth_url)
        time.sleep(3)

        # --- 2. 画面リフレッシュ ---
        print("画面を再読み込みします...")
        driver.get(auth_url)
        time.sleep(5)

        # --- 3. 「絞り込み検索」ボタンをクリック ---
        print("検索メニューを開きます...")
        try:
            filter_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '絞り込み検索')]")))
            filter_btn.click()
            time.sleep(3)
        except:
            pass

        # --- 4. 登録日時の「本日」ボタンをクリック ---
        print("登録日時の「本日」ボタンをクリックします...")
        try:
            today_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button.btn.btn-secondary.btn-sm.today")
            ))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", today_btn)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", today_btn)
            print("「本日」ボタンをクリックしました")
            time.sleep(1)
        except Exception as e:
            print(f"「本日」ボタンのクリックエラー: {e}")

        # --- 5. パートナーを入力 ---
        print("パートナーを入力します...")
        try:
            partner_label = driver.find_element(By.XPATH, "//div[contains(text(), 'パートナー')] | //label[contains(text(), 'パートナー')]")
            partner_target = partner_label.find_element(By.XPATH, "./following::input[contains(@placeholder, '選択')][1]")
            partner_target.click()
            time.sleep(1)
            
            active_elem = driver.switch_to.active_element
            active_elem.send_keys("株式会社フルアウト")
            time.sleep(3)
            active_elem.send_keys(Keys.ENTER)
            print("パートナーを選択しました")
            time.sleep(2)
        except Exception as e:
            print(f"パートナー入力エラー: {e}")

        # --- 6. 検索ボタン実行 ---
        print("検索ボタンを探して押します...")
        try:
            search_btns = driver.find_elements(By.XPATH, "//input[@value='検索'] | //button[contains(text(), '検索')]")
            target_search_btn = None
            for btn in search_btns:
                if btn.is_displayed():
                    target_search_btn = btn
            
            if target_search_btn:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_search_btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", target_search_btn)
                print("検索ボタンをクリックしました")
            else:
                webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()
        except Exception as e:
            print(f"検索ボタン操作エラー: {e}")
        
        # --- 検索結果の反映待ち ---
        print("検索結果を待機中...")
        time.sleep(15)

        # --- 7. CSV生成ボタン ---
        print("CSV生成ボタンを押します...")
        try:
            csv_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@value='CSV生成' or contains(text(), 'CSV生成')]")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", csv_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", csv_btn)
            print("CSV生成ボタンをクリックしました")
        except Exception as e:
            print(f"CSVボタンエラー: {e}")
            return
        
        # ダウンロード待ち
        print("ダウンロード待機中...")
        time.sleep(8)
        for i in range(30):
            files = glob.glob(os.path.join(download_dir, "*.csv"))
            if files:
                break
            time.sleep(3)
            
        files = glob.glob(os.path.join(download_dir, "*.csv"))
        if not files:
            print("【エラー】CSVファイルが見つかりません。")
            return
        
        csv_file_path = files[0]
        print(f"ダウンロード成功: {csv_file_path}")

        # --- 8. Google Driveへアップロード ---
        upload_to_drive(csv_file_path)

    except Exception as e:
        print(f"【エラー発生】: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
