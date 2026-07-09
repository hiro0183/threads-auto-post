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

# DB永続化（Render再デプロイでトークンが巻き戻るのを防ぐ）。
# DATABASE_URL未設定のローカルでは load/save が自動でファイルベースにフォールバックする。
try:
    from db_state import load_token_from_db, save_token_to_db
except Exception:
    load_token_from_db = None
    save_token_to_db = None


def load_tokens() -> dict:
    # 1. DB優先（Render本番。再デプロイをまたいでリフレッシュ済みトークンが残る）
    if load_token_from_db:
        try:
            data = load_token_from_db()
            if data and data.get("access_token"):
                return data
        except Exception as e:
            print(f"[TOKEN] DB読み込み失敗 → ファイル/envにフォールバック: {e}")

    # 2. ローカルtokens.json
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            data = json.load(f)
        _seed_db_if_possible(data)  # DBが空なら初期投入
        return data

    # 3. .env の種トークン（初回のみ。以降はDB/ファイルが正）
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    if token:
        data = {
            "access_token": token,
            "token_type": "bearer",
            "refreshed_at": datetime.now().isoformat(),
        }
        save_tokens(data)  # ファイル＋DBに保存
        return data
    raise RuntimeError("トークンが見つかりません。.env または DB を確認してください。")


def _seed_db_if_possible(data: dict):
    """DBが利用可能なら現在のトークンを投入する（load_tokensがDBで空振りした後に呼ばれる）"""
    if save_token_to_db:
        try:
            save_token_to_db(data)
        except Exception:
            pass


def save_tokens(data: dict):
    # DB優先で保存（本番の永続化先）。失敗してもファイルには必ず残す。
    if save_token_to_db:
        try:
            save_token_to_db(data)
        except Exception as e:
            print(f"[TOKEN] DB保存失敗（ファイルにフォールバック）: {e}")
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
    import sys
    if "--seed" in sys.argv:
        # 手動再認証の直後に使う：ローカルtokens.json / .env のトークンを
        # 強制的にDBへ発行して本番の値を差し替える（DATABASE_URLが必要）。
        seed = None
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE) as f:
                seed = json.load(f)
        elif os.environ.get("THREADS_ACCESS_TOKEN"):
            seed = {
                "access_token": os.environ["THREADS_ACCESS_TOKEN"],
                "token_type": "bearer",
                "refreshed_at": datetime.now().isoformat(),
            }
        if not seed:
            print("種にするトークンが見つかりません（tokens.json / .env）")
            sys.exit(1)
        if save_token_to_db and save_token_to_db(seed):
            print("[SEED] 現在のトークンをDBに発行しました")
        else:
            print("[SEED] DB保存に失敗（DATABASE_URL未設定？）")
    else:
        check_and_refresh()
