"""
Threads自動投稿ランナー（ツリー投稿対応）
Windowsタスクスケジューラから呼び出されて1ツリー（3連投）を投稿する

使い方:
  python post_runner.py          # AI生成してツリー投稿
  python post_runner.py --dry    # 内容確認のみ（投稿しない）
  python post_runner.py --refresh # トークン更新のみ
  python post_runner.py --logs   # 投稿ログ確認
"""

import os
import sys
import json
import time
import requests
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "post_log.jsonl"

logging.basicConfig(
    filename=BASE_DIR / "error.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)


# ── Threads API ────────────────────────────────────────

def get_user_id(token: str) -> str:
    resp = requests.get(
        "https://graph.threads.net/v1.0/me",
        params={"fields": "id,username", "access_token": token},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def create_container(text: str, token: str, user_id: str, reply_to_id: str = None) -> str:
    """投稿コンテナを作成してcontainer_idを返す"""
    data = {
        "media_type": "TEXT",
        "text": text,
        "access_token": token,
    }
    if reply_to_id:
        data["reply_to_id"] = reply_to_id

    resp = requests.post(
        f"https://graph.threads.net/v1.0/{user_id}/threads",
        data=data,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_container(container_id: str, token: str, user_id: str) -> str:
    """コンテナを公開して投稿IDを返す"""
    resp = requests.post(
        f"https://graph.threads.net/v1.0/{user_id}/threads_publish",
        data={"creation_id": container_id, "access_token": token},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def post_single(text: str, token: str, user_id: str, reply_to_id: str = None) -> str:
    """1件投稿してpost_idを返す"""
    container_id = create_container(text, token, user_id, reply_to_id)
    time.sleep(2)  # API安定のため少し待つ
    post_id = publish_container(container_id, token, user_id)
    return post_id


def post_thread(posts: list[str], token: str, user_id: str) -> list[str]:
    """ツリー投稿（3連投）を実行してpost_idリストを返す"""
    post_ids = []
    reply_to = None

    for i, text in enumerate(posts):
        post_id = post_single(text, token, user_id, reply_to_id=reply_to)
        post_ids.append(post_id)
        reply_to = post_id
        print(f"  [{i+1}/{len(posts)}] 投稿完了: {post_id}")
        if i < len(posts) - 1:
            time.sleep(3)  # 連投の間隔

    return post_ids


# ── ログ ───────────────────────────────────────────────

def write_log(post_ids: list, posts: list[str], status: str, error: str = None):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "post_ids": post_ids,
        "preview": posts[0][:50].replace("\n", " ") if posts else "",
        "error": error,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def show_recent_logs(n: int = 10):
    if not LOG_FILE.exists():
        print("ログなし")
        return
    lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
    for line in lines[-n:]:
        entry = json.loads(line)
        mark = "✅" if entry["status"] == "ok" else "❌"
        print(f"{mark} {entry['timestamp'][:16]}  {entry['preview']}")


# ── 事前生成ファイル読み込み ────────────────────────────

def load_scheduled_post() -> list[str] | None:
    """今日の現在時刻に対応する事前生成投稿を返す。なければNone"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    json_file = BASE_DIR / "posts" / f"{date_str}.json"
    if not json_file.exists():
        return None

    with open(json_file, encoding="utf-8") as f:
        schedule = json.load(f)

    # 現在時刻±5分以内のスロットを探す
    from datetime import timedelta
    now_t = now.replace(second=0, microsecond=0)
    for slot_time, posts in schedule.items():
        h, m = map(int, slot_time.split(":"))
        slot_dt = now_t.replace(hour=h, minute=m)
        diff = abs((now_t - slot_dt).total_seconds())
        if diff <= 300 and posts:
            print(f"  スロット {slot_time} の投稿を使用")
            return posts

    return None


# ── メイン ─────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    dry_run = "--dry" in args
    refresh_only = "--refresh" in args
    show_logs = "--logs" in args

    if show_logs:
        show_recent_logs()
        return

    # トークン取得・更新
    from token_manager import check_and_refresh
    token = check_and_refresh()

    if refresh_only:
        print("トークン更新完了")
        return

    # コンテンツ取得（事前生成ファイル優先 → なければAI生成）
    posts = load_scheduled_post()
    if posts:
        print(f"[{datetime.now().strftime('%H:%M')}] 事前生成ファイルから投稿を読み込みました")
    else:
        from content_generator import generate_thread
        print(f"[{datetime.now().strftime('%H:%M')}] ファイルなし → AI生成中...")
        posts = generate_thread()

    print("\n--- 生成内容 ---")
    for i, post in enumerate(posts, 1):
        print(f"\n【{i}投稿目】")
        print(post)

    if dry_run:
        print("\n[DRY RUN] 実際には投稿しません")
        return

    # 投稿
    print("\n投稿中...")
    try:
        user_id = get_user_id(token)
        post_ids = post_thread(posts, token, user_id)
        print(f"\n[OK] ツリー投稿完了（{len(post_ids)}件）")
        write_log(post_ids, posts, "ok")
    except Exception as e:
        error_msg = str(e)
        print(f"\n[ERROR] 投稿失敗: {error_msg}")
        logging.error(f"投稿失敗: {error_msg}\n内容: {posts[0][:100]}")
        write_log([], posts, "error", error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
