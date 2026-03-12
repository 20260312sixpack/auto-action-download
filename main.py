import os
import json
import time
import glob
from datetime import datetime, timedelta, timezone
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
DRIVE_FOLDER_ID = "1NypwP4Tz5oMzjDUBc21fBu7ijDICfzS3"
SCREENSHOT_DIR = os.path.join(os.getcwd(), "screenshots")

def save_screenshot(driver, step_name):
    """スクリーンショットを保存してログ出力"""
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
    filename = f"{step_name}_{int(time.time())}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    driver.save_screenshot(filepath)
    print(f"[スクリーンショット] {step_name}: {filepath}")
    return filepath

def upload_to_drive(file_path):
    """Google Driveにファイルをアップロードする関数"""
    print(f"ドライブへのアップロードを開始: {file_path}")
    
    scopes = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(json_creds, scopes=scopes)
    service = build('drive', 'v3', credentials=creds)

    file_name = os.path.basename(file_path)
    
    # 拡張子でMIMEタイプを判定
    if file_name.endswith('.png'):
        mimetype = 'image/png'
    else:
        mimetype = 'text/csv'
    
    file_metadata = {
        'name': file_name,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype=mimetype)

    file = service.files().create(
        body=file_metadata, 
        media_body=media, 
        fields='id', 
        supportsAllDrives=True
    ).execute()
    
    print(f"アップロード完了 File ID: {file.get('id')}")

def get_today_jst():
    """日本時間の本日を計算して文字列で返す"""
    JST = timezone(timedelta(hours=+9), 'JST')
    now = datetime.now(JST)
    return now.strftime("%Y年%m月%d日")

def main():
    print("=== Ad Report CSV取得処理開始 ===")
    
    # 日本時間の本日を表示
    JST = timezone(timedelta(hours=+9), 'JST')
    now_jst = datetime.now(JST)
    now_utc = datetime.now(timezone.utc)
    print(f"現在時刻(JST): {now_jst.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"現在時刻(UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"本日の日付(JST): {get_today_jst()}")
    
    download_dir = os.path.join(os.getcwd(), "downloads_report")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    # タイムゾーンを日本時間に設定
    options.add_argument('--timezone=Asia/Tokyo')
    
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # ブラウザのタイムゾーンをJSTに上書き
    driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'Asia/Tokyo'})
    print("ブラウザのタイムゾーンをAsia/Tokyoに設定しました")
    
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
        save_screenshot(driver, "01_初回アクセス")

        # --- 2. 画面リフレッシュ ---
        print("画面を再読み込みします...")
        driver.refresh()
        time.sleep(5)
        
        # ブラウザ上のJavaScript日付を確認
        browser_date = driver.execute_script("return new Date().toString();")
        print(f"ブラウザ内の日付: {browser_date}")
        save_screenshot(driver, "02_リフレッシュ後")

        # --- 3. 「絞り込み検索」ボタンをクリック ---
        print("検索メニューを開きます...")
        try:
            filter_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '絞り込み検索')]")))
            filter_btn.click()
            time.sleep(3)
            save_screenshot(driver, "03_絞り込み検索展開後")
        except Exception as e:
            print(f"絞り込み検索ボタンエラー: {e}")
            save_screenshot(driver, "03_絞り込み検索エラー")

        # --- 4. 登録日時の「本日」ボタンをクリック ---
        print("登録日時の「本日」ボタンをクリックします...")
        try:
            # 「本日」ボタンを探す
            today_btns = driver.find_elements(By.CSS_SELECTOR, "button.btn.btn-secondary.btn-sm.today")
            print(f"「本日」ボタンの数: {len(today_btns)}")
            
            for i, btn in enumerate(today_btns):
                print(f"  ボタン{i}: text='{btn.text}', displayed={btn.is_displayed()}, location={btn.location}")
            
            if today_btns:
                today_btn = today_btns[0]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", today_btn)
                time.sleep(0.5)
                save_screenshot(driver, "04a_本日ボタンクリック前")
                
                driver.execute_script("arguments[0].click();", today_btn)
                print("「本日」ボタンをクリックしました")
                time.sleep(2)
                save_screenshot(driver, "04b_本日ボタンクリック後")
                
                # 日付入力欄の値を確認
                date_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                for i, inp in enumerate(date_inputs):
                    val = inp.get_attribute("value")
                    if val and ("年" in val or "20" in val or "-" in val):
                        print(f"  日付入力欄{i}: value='{val}'")
            else:
                print("「本日」ボタンが見つかりません")
                save_screenshot(driver, "04_本日ボタンなし")

        except Exception as e:
            print(f"「本日」ボタンのクリックエラー: {e}")
            save_screenshot(driver, "04_本日ボタンエラー")

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
            save_screenshot(driver, "05_パートナー選択後")
        except Exception as e:
            print(f"パートナー入力エラー: {e}")
            save_screenshot(driver, "05_パートナーエラー")

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
                save_screenshot(driver, "06a_検索ボタンクリック前")
                driver.execute_script("arguments[0].click();", target_search_btn)
                print("検索ボタンをクリックしました")
            else:
                webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()
        except Exception as e:
            print(f"検索ボタン操作エラー: {e}")
            save_screenshot(driver, "06_検索ボタンエラー")
        
        # --- 検索結果の反映待ち ---
        print("検索結果を待機中...")
        time.sleep(15)
        save_screenshot(driver, "07_検索結果表示後")

        # --- 7. CSV生成ボタン ---
        print("CSV生成ボタンを押します...")
        try:
            csv_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@value='CSV生成' or contains(text(), 'CSV生成')]")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", csv_btn)
            time.sleep(1)
            save_screenshot(driver, "08a_CSV生成ボタンクリック前")
            driver.execute_script("arguments[0].click();", csv_btn)
            print("CSV生成ボタンをクリックしました")
        except Exception as e:
            print(f"CSVボタンエラー: {e}")
            save_screenshot(driver, "08_CSVボタンエラー")
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
            save_screenshot(driver, "09_CSVダウンロード失敗")
            return
        
        csv_file_path = files[0]
        print(f"ダウンロード成功: {csv_file_path}")

        # --- 8. Google Driveへアップロード（CSV） ---
        upload_to_drive(csv_file_path)
        
        # --- 9. スクリーンショットもDriveにアップロード ---
        print("スクリーンショットをアップロード中...")
        screenshots = glob.glob(os.path.join(SCREENSHOT_DIR, "*.png"))
        for ss_file in sorted(screenshots):
            upload_to_drive(ss_file)

    except Exception as e:
        print(f"【エラー発生】: {e}")
        import traceback
        traceback.print_exc()
        save_screenshot(driver, "99_エラー発生時")
        # エラー時のスクリーンショットもアップロード
        try:
            screenshots = glob.glob(os.path.join(SCREENSHOT_DIR, "*.png"))
            for ss_file in sorted(screenshots):
                upload_to_drive(ss_file)
        except:
            pass
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
