"""
Threads APIでフォロワー数を日次取得してObsidianに記録するスクリプト

使い方:
  python track_followers.py        # 今日のフォロワー数を記録
  python track_followers.py --show # ログを表示するだけ
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
FOLLOWER_LOG_FILE = BASE_DIR / "follower_log.jsonl"
OBSIDIAN_CONSULT_DIR = Path(r"C:\Users\tujid\OneDrive\Desktop\HIRAYASU\コンサルThreads")

JST = timezone(timedelta(hours=9))


def get_follower_count(token: str) -> int | None:
    me = requests.get(
        "https://graph.threads.net/v1.0/me",
        params={"fields": "id", "access_token": token},
    )
    if me.status_code != 200:
        print(f"APIエラー(user_id取得): {me.status_code} {me.text}")
        return None
    user_id = me.json().get("id")

    # followers_countはプロフィールfieldsではなくthreads_insightsのmetricとしてのみ取得可能
    resp = requests.get(
        f"https://graph.threads.net/v1.0/{user_id}/threads_insights",
        params={"metric": "followers_count", "access_token": token},
    )
    if resp.status_code != 200:
        print(f"APIエラー: {resp.status_code} {resp.text}")
        return None
    data = resp.json().get("data", [])
    if not data:
        print("APIエラー: followers_countデータが空")
        return None
    return data[0].get("total_value", {}).get("value")


def load_log() -> list:
    if not FOLLOWER_LOG_FILE.exists():
        return []
    rows = []
    for line in FOLLOWER_LOG_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def write_obsidian(rows: list):
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    lines = [f"# フォロワー推移\n"]
    lines.append(f"> 更新: {now_str}\n")
    lines.append("## 推移\n")
    lines.append("| 日付 | フォロワー数 | 前日比 |")
    lines.append("|:---:|---:|---:|")

    for i, row in enumerate(rows):
        prev = rows[i - 1]["count"] if i > 0 else row["count"]
        diff = row["count"] - prev
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        lines.append(f"| {row['date']} | {row['count']:,} | {diff_str} |")

    md_file = OBSIDIAN_CONSULT_DIR / "フォロワー推移.md"
    md_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"保存: {md_file}")


def main():
    if "--show" in sys.argv:
        rows = load_log()
        for r in rows[-10:]:
            print(r)
        return

    from token_manager import check_and_refresh
    token = check_and_refresh()

    today = datetime.now(JST).strftime("%Y-%m-%d")

    # 今日分が既にあればスキップ
    rows = load_log()
    if rows and rows[-1].get("date") == today:
        print(f"今日({today})は取得済み: {rows[-1]['count']:,}人")
        write_obsidian(rows)
        return

    count = get_follower_count(token)
    if count is None:
        print("フォロワー数の取得に失敗しました")
        return

    print(f"{today}: {count:,}人")

    with open(FOLLOWER_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"date": today, "count": count}) + "\n")

    rows = load_log()
    write_obsidian(rows)


if __name__ == "__main__":
    main()
