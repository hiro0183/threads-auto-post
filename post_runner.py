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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "post_log.jsonl"
STATE_DIR = BASE_DIR / "state"
OBSIDIAN_THREADS_DIR = Path(os.environ.get("OBSIDIAN_DIR", r"C:\Users\tujid\iCloudDrive\HIRAYASU\コンサルThreads\投稿履歴"))

# 投稿スケジュール（JST）
POST_SCHEDULE = [
    "05:45", "06:00", "07:00", "07:30", "08:00", "08:30",
    "09:00", "09:30", "10:00", "11:00", "12:00", "12:30",
    "13:00", "14:00", "15:00", "16:00", "17:00", "18:00",
    "18:30", "19:00", "19:15", "19:30", "20:00", "20:15",
    "20:20", "20:40", "21:00", "21:20", "21:40", "22:00",
]

def load_posted_state(date_str: str) -> set:
    """今日の投稿済みスロットのセットを返す"""
    state_file = STATE_DIR / f"{date_str}.json"
    if not state_file.exists():
        return set()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    return set(data.get("posted", []))


def save_posted_state(date_str: str, slot: str):
    """投稿済みスロットを記録する"""
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{date_str}.json"
    posted = load_posted_state(date_str)
    posted.add(slot)
    jst = timezone(timedelta(hours=9))
    data = {
        "posted": sorted(posted),
        "updated": datetime.now(jst).isoformat(),
    }
    state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def find_target_slot() -> str | None:
    """投稿すべきスロットを返す（現在時刻以前で最も新しい未投稿スロット）"""
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    date_str = now.strftime("%Y-%m-%d")
    now_min = now.hour * 60 + now.minute

    posted = load_posted_state(date_str)

    target = None
    for slot in POST_SCHEDULE:
        h, m = map(int, slot.split(":"))
        slot_min = h * 60 + m
        if slot_min <= now_min and slot not in posted:
            target = slot  # より新しいものに上書き

    if target:
        print(f"[スケジュール] {target} を投稿します（現在 {now.strftime('%H:%M')} JST）")
    else:
        print(f"[スキップ] 投稿すべきスロットなし（現在 {now.strftime('%H:%M')} JST）")
    return target

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
        timeout=30,
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
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_container(container_id: str, token: str, user_id: str) -> str:
    """コンテナを公開して投稿IDを返す"""
    resp = requests.post(
        f"https://graph.threads.net/v1.0/{user_id}/threads_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=30,
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

def write_obsidian(posts: list[str], post_time: str):
    """投稿内容をObsidianの日付ファイルに追記する"""
    try:
        OBSIDIAN_THREADS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        md_file = OBSIDIAN_THREADS_DIR / f"{date_str}.md"

        header = f"## {post_time}\n\n"
        body = "\n\n---\n\n".join(posts)
        entry = f"{header}{body}\n\n---\n\n"

        if not md_file.exists():
            md_file.write_text(f"# {date_str} 投稿履歴\n\n", encoding="utf-8")

        with open(md_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        logging.error(f"Obsidian書き込み失敗: {e}")


def write_log(post_ids: list, posts: list[str], status: str, error: str = None, slot: str = None):
    jst = timezone(timedelta(hours=9))
    entry = {
        "timestamp": datetime.now(jst).isoformat(),
        "slot": slot or datetime.now(jst).strftime("%H:%M"),
        "status": status,
        "post_ids": post_ids,
        "posts": posts,  # 全文保存（インサイト集計で使用）
        "post_type": "single" if len(posts) == 1 else "tree",
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
        mark = "[OK]" if entry["status"] == "ok" else "[NG]"
        preview = entry.get("posts", [""])[0][:30] if entry.get("posts") else ""
        print(f"{mark} {entry['timestamp'][:16]}  {preview}")


# ── スロット計画（ツリー22件・単体8件・CTA6件/日）──────────
# type: "tree" or "single" / cta: True → 3投稿目にLINE CTA追加

SLOT_PLAN = {
    "05:45": {"type": "tree",   "cta": False},
    "06:00": {"type": "single", "cta": False},
    "07:00": {"type": "tree",   "cta": False},
    "07:30": {"type": "tree",   "cta": False},
    "08:00": {"type": "tree",   "cta": True},   # CTA 1
    "08:30": {"type": "single", "cta": False},
    "09:00": {"type": "tree",   "cta": False},
    "09:30": {"type": "tree",   "cta": False},
    "10:00": {"type": "tree",   "cta": True},   # CTA 2
    "11:00": {"type": "single", "cta": False},
    "12:00": {"type": "tree",   "cta": False},
    "12:30": {"type": "tree",   "cta": True},   # CTA 3
    "13:00": {"type": "tree",   "cta": False},
    "14:00": {"type": "single", "cta": False},
    "15:00": {"type": "tree",   "cta": False},
    "16:00": {"type": "tree",   "cta": True},   # CTA 4
    "17:00": {"type": "tree",   "cta": True},   # CTA 5
    "18:00": {"type": "tree",   "cta": False},
    "18:30": {"type": "single", "cta": False},
    "19:00": {"type": "tree",   "cta": True},   # CTA 6
    "19:15": {"type": "tree",   "cta": False},
    "19:30": {"type": "tree",   "cta": False},
    "20:00": {"type": "single", "cta": False},
    "20:15": {"type": "tree",   "cta": False},
    "20:20": {"type": "tree",   "cta": True},   # CTA 7
    "20:40": {"type": "single", "cta": False},
    "21:00": {"type": "tree",   "cta": False},
    "21:20": {"type": "tree",   "cta": True},   # CTA 8
    "21:40": {"type": "tree",   "cta": False},
    "22:00": {"type": "single", "cta": False},
}


def get_slot_info(slot: str) -> dict:
    """スロット名に対応する計画を返す。なければtree/cta=Falseをデフォルト返却"""
    return SLOT_PLAN.get(slot, {"type": "tree", "cta": False})


# ── 事前生成ファイル読み込み ────────────────────────────

def load_scheduled_post(target_slot: str) -> list[str] | None:
    """指定スロットの事前生成投稿を返す。なければNone"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    json_file = BASE_DIR / "posts" / f"{date_str}.json"
    if not json_file.exists():
        return None

    try:
        schedule = json.loads(json_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [WARN] JSONファイル読み込み失敗: {e} → AI生成にフォールバック")
        return None
    posts = schedule.get(target_slot)
    if posts:
        print(f"  スロット {target_slot} の事前生成投稿を使用")
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

    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    date_str = now.strftime("%Y-%m-%d")

    # 投稿対象スロットの決定
    if dry_run or refresh_only:
        # dry run / refresh 時は現在時刻に最も近いスロットを使う
        now_min = now.hour * 60 + now.minute
        target_slot = min(POST_SCHEDULE, key=lambda s: abs(now_min - int(s[:2]) * 60 - int(s[3:])))
    else:
        target_slot = find_target_slot()
        if not target_slot:
            sys.exit(0)

    # トークン取得・更新
    from token_manager import check_and_refresh
    token = check_and_refresh()

    if refresh_only:
        print("トークン更新完了")
        return

    # コンテンツ取得（事前生成ファイル優先 → なければAI生成）
    posts = load_scheduled_post(target_slot)
    if posts:
        print(f"[{target_slot}] 事前生成ファイルから読み込みました")
    else:
        from content_generator import generate_thread, generate_single_post
        slot_info = get_slot_info(target_slot)
        print(f"[{target_slot}] ファイルなし → AI生成中... ({slot_info['type']}{', CTA' if slot_info['cta'] else ''})")
        if slot_info["type"] == "single":
            posts = generate_single_post()
        else:
            posts = generate_thread(cta=slot_info["cta"])

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
        print(f"\n[OK] 投稿完了（{len(post_ids)}件） slot={target_slot}")
        write_log(post_ids, posts, "ok", slot=target_slot)
        write_obsidian(posts, target_slot)
        save_posted_state(date_str, target_slot)
        print(f"[STATE] {target_slot} を投稿済みとして記録")
    except Exception as e:
        error_msg = str(e)
        print(f"\n[ERROR] 投稿失敗: {error_msg}")
        logging.error(f"投稿失敗: {error_msg}\n内容: {posts[0][:100]}")
        write_log([], posts, "error", error_msg, slot=target_slot)
        sys.exit(1)


if __name__ == "__main__":
    main()
