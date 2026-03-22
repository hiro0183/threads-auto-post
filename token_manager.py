"""
Threadsトークン自動更新マネージャー
- 長期トークン（60日）を自動でリフレッシュして「期限なし」に近い状態を維持
- Windowsタスクスケジューラで月1回実行することを想定
"""

import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "tokens.json")


def load_tokens() -> dict:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    # .envのトークンをtokens.jsonに初期保存
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    if token:
        data = {
            "access_token": token,
            "token_type": "bearer",
            "refreshed_at": datetime.now().isoformat(),
        }
        save_tokens(data)
        return data
    raise RuntimeError("トークンが見つかりません。.envを確認してください。")


def save_tokens(data: dict):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_access_token() -> str:
    return load_tokens()["access_token"]


def refresh_token() -> str:
    """長期トークンをリフレッシュして60日延長"""
    tokens = load_tokens()
    current_token = tokens["access_token"]

    resp = requests.get(
        "https://graph.threads.net/refresh_access_token",
        params={
            "grant_type": "th_refresh_token",
            "access_token": current_token,
        },
    )

    if resp.status_code != 200:
        print(f"[ERROR] トークンリフレッシュ失敗: {resp.text}")
        return current_token

    new_data = resp.json()
    new_data["refreshed_at"] = datetime.now().isoformat()
    new_data["expires_at"] = (datetime.now() + timedelta(seconds=new_data.get("expires_in", 5184000))).isoformat()
    save_tokens(new_data)

    print(f"[OK] トークンをリフレッシュしました: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"     次回期限: {new_data['expires_at']}")
    return new_data["access_token"]


def check_and_refresh():
    """期限30日以内なら自動リフレッシュ"""
    tokens = load_tokens()
    expires_at = tokens.get("expires_at")

    if not expires_at:
        print("[INFO] 期限情報なし → リフレッシュ実行")
        return refresh_token()

    expires_dt = datetime.fromisoformat(expires_at)
    days_left = (expires_dt - datetime.now()).days

    print(f"[INFO] トークン残り日数: {days_left}日")

    if days_left <= 30:
        print("[INFO] 30日以内のため自動リフレッシュ")
        return refresh_token()
    else:
        print("[INFO] リフレッシュ不要")
        return tokens["access_token"]


if __name__ == "__main__":
    check_and_refresh()
