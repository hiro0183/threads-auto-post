"""
投稿から24時間後にThreads APIでインサイトを取得し、
Obsidianに投稿内容＋分析テーブルとして保存するスクリプト

毎朝6:00にタスクスケジューラから自動実行
使い方:
  python collect_insights.py          # 24時間以上経過した未集計投稿を処理
  python collect_insights.py --all    # 全投稿を再集計
"""

import os
import sys
import json
import requests
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

IS_RENDER = bool(os.environ.get("RENDER"))

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "post_log.jsonl"
COLLECTED_FILE = BASE_DIR / "insights_collected.jsonl"
INSIGHTS_DATA_FILE = BASE_DIR / "insights_data.jsonl"
OBSIDIAN_INSIGHTS_DIR = Path(r"C:\Users\tujid\iCloudDrive\HIRAYASU\コンサルThreads\インサイト")

logging.basicConfig(
    filename=BASE_DIR / "insights.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

JST = timezone(timedelta(hours=9))


def get_insights(post_id: str, token: str) -> dict:
    """指定post_idのインサイトを取得"""
    resp = requests.get(
        f"https://graph.threads.net/v1.0/{post_id}/insights",
        params={
            "metric": "views,likes,replies,reposts,quotes",
            "access_token": token,
        },
    )
    if resp.status_code != 200:
        return {}

    data = resp.json().get("data", [])
    result = {}
    for item in data:
        result[item["name"]] = item.get("values", [{}])[0].get("value", 0) if "values" in item else item.get("value", 0)
    return result


def load_collected_ids() -> set:
    """集計済みのpost_idセットを返す"""
    if not COLLECTED_FILE.exists():
        return set()
    ids = set()
    for line in COLLECTED_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            try:
                ids.add(json.loads(line)["root_post_id"])
            except Exception:
                pass
    return ids


def mark_collected(root_post_id: str, date_str: str):
    """集計済みとしてマーク"""
    with open(COLLECTED_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"root_post_id": root_post_id, "date": date_str}) + "\n")


def write_obsidian(date_str: str, rows: list):
    """ObsidianにMarkdownテーブルとして書き出す（Render環境ではスキップ）"""
    if IS_RENDER:
        return
    OBSIDIAN_INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    md_file = OBSIDIAN_INSIGHTS_DIR / f"{date_str}.md"

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"# {date_str} 投稿インサイト\n")
    lines.append(f"> 集計日時: {now_str}\n")

    # サマリーテーブル
    lines.append("## 一覧\n")
    lines.append("| 時刻 | 種別 | キャッチ（1投稿目） | Views | Likes | Replies | Reposts | Quotes | エンゲージ計 |")
    lines.append("|:---:|:---:|:---|---:|---:|---:|---:|---:|---:|")

    for row in rows:
        kind = "ツリー" if row["post_type"] == "tree" else "単体"
        catch = row["catch"][:25] + "…" if len(row["catch"]) > 25 else row["catch"]
        v = row.get("views", "-")
        l = row.get("likes", "-")
        r = row.get("replies", "-")
        rp = row.get("reposts", "-")
        q = row.get("quotes", "-")
        eng = sum(x for x in [l, r, rp, q] if isinstance(x, int))
        lines.append(f"| {row['slot']} | {kind} | {catch} | {v:,} | {l} | {r} | {rp} | {q} | {eng} |")

    # 上位3投稿の詳細
    valid = [r for r in rows if isinstance(r.get("views"), int)]
    top3 = sorted(valid, key=lambda x: x.get("views", 0), reverse=True)[:3]

    if top3:
        lines.append("\n## 上位3投稿（Views）\n")
        for i, row in enumerate(top3, 1):
            lines.append(f"### {i}位 {row['slot']}（Views: {row.get('views', 0):,}）\n")
            for j, p in enumerate(row["posts"], 1):
                label = f"{j}投稿目" if row["post_type"] == "tree" else "本文"
                lines.append(f"**{label}:**")
                lines.append(f"{p}\n")

    md_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"Obsidian保存: {md_file}")


def main():
    force_all = "--all" in sys.argv

    if not LOG_FILE.exists():
        print("投稿ログがありません")
        return

    from token_manager import check_and_refresh
    token = check_and_refresh()

    collected_ids = set() if force_all else load_collected_ids()
    now = datetime.now(JST)

    # ログ読み込み
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass

    # 24時間以上経過 & 未集計 & 成功した投稿を対象
    targets = []
    for entry in entries:
        if entry.get("status") != "ok":
            continue
        if not entry.get("post_ids"):
            continue
        root_id = entry["post_ids"][0]
        if root_id in collected_ids:
            continue
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=JST)
        except Exception:
            continue
        if (now - ts).total_seconds() < 86400:  # 24時間未満はスキップ
            continue
        targets.append(entry)

    if not targets:
        print("集計対象の投稿がありません（24時間未満または集計済み）")
        return

    print(f"集計対象: {len(targets)}件")

    # 日付ごとにグループ化
    by_date = {}
    for entry in targets:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=JST)
        except Exception:
            continue
        date_str = ts.strftime("%Y-%m-%d")
        by_date.setdefault(date_str, []).append(entry)

    for date_str, day_entries in sorted(by_date.items()):
        rows = []
        for entry in sorted(day_entries, key=lambda x: x.get("slot", "")):
            root_id = entry["post_ids"][0]
            print(f"  {entry.get('slot', '??:??')} インサイト取得中...")

            insights = get_insights(root_id, token)

            row = {
                "slot": entry.get("slot", "??:??"),
                "post_type": entry.get("post_type", "tree"),
                "catch": (entry.get("posts") or [""])[0].replace("\n", " "),
                "posts": entry.get("posts", []),
                "root_id": root_id,
                **insights,
            }
            rows.append(row)
            mark_collected(root_id, date_str)

        write_obsidian(date_str, rows)
        # ローカルにも構造化データを保存（パターン分析用）
        with open(INSIGHTS_DATA_FILE, "a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps({**row, "date": date_str}, ensure_ascii=False) + "\n")
        print(f"  {date_str}: {len(rows)}件 集計完了")

    print("\n全集計完了")

    if IS_RENDER:
        from github_sync import sync_all
        sync_all()


if __name__ == "__main__":
    main()
