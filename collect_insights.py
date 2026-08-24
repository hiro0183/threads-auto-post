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
OBSIDIAN_INSIGHTS_DIR = Path(r"C:\Users\tujid\OneDrive\Desktop\HIRAYASU\コンサルThreads\インサイト")

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
        v_str = f"{v:,}" if isinstance(v, int) else str(v)
        lines.append(f"| {row['slot']} | {kind} | {catch} | {v_str} | {l} | {r} | {rp} | {q} | {eng} |")

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


def load_collected_from_insights() -> set:
    """insights_data.jsonl から集計済みroot_idを復元する。

    insights_collected.jsonl はRenderの揮発ディスク上にあり再起動で消えるため、
    GitHubへ同期される insights_data.jsonl を第二の台帳として併用する。
    """
    ids = set()
    if not INSIGHTS_DATA_FILE.exists():
        return ids
    for line in INSIGHTS_DATA_FILE.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        try:
            rid = json.loads(line).get("root_id")
        except Exception:
            continue
        if rid:
            ids.add(rid)
    return ids


def _tree_text_for(date_str: str, slot: str) -> list:
    """posts/{date}.json から該当スロットのツリー全文を返す（無ければ空）"""
    f = BASE_DIR / "posts" / f"{date_str}.json"
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8")).get(slot) or []
    except Exception:
        return []


def targets_from_api(token: str, collected: set, days: int = 14) -> list:
    """Threads APIの実投稿を起点に集計対象を組み立てる（2026-08-24新設・こちらが正）。

    従来は post_log.jsonl（Renderの揮発ディスク上のファイル）を起点にしていたため、
    再起動やPOST_SCHEDULEのズレでログが欠けると計測ごと止まった。実際に
    2026-08-03〜24はログに成功記録が一件も残らず、実測が8/2で凍結した。
    Threads API は投稿そのものが台帳なので、この経路は落ちても復元できる。
    """
    from reach_check import fetch_recent_posts, _match_slot
    from post_runner import SLOT_PLAN

    slots = list(SLOT_PLAN.keys())
    now = datetime.now(JST)
    posts = fetch_recent_posts(token, limit=100)

    targets = []
    for p in posts:
        if p["id"] in collected:
            continue
        if (now - p["jst"]).total_seconds() < 86400:  # 24時間未満は数字が固まらない
            continue
        if (now - p["jst"]).days > days:
            continue
        date_str = p["jst"].date().isoformat()
        slot = _match_slot(p["jst"], slots) or p["jst"].strftime("%H:%M")
        tree = _tree_text_for(date_str, slot) or [p["text"]]
        targets.append({
            "timestamp": p["jst"].isoformat(),
            "date": date_str,
            "slot": slot,
            "post_type": "tree" if len(tree) > 1 else "single",
            "posts": tree,
            "post_ids": [p["id"]],
        })
    return targets


def targets_from_log(collected: set) -> list:
    """従来経路: post_log.jsonl の成功投稿から集計対象を組み立てる（補助）"""
    if not LOG_FILE.exists():
        return []
    now = datetime.now(JST)
    out = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("status") != "ok" or not entry.get("post_ids"):
            continue
        root_id = entry["post_ids"][0]
        if root_id in collected:
            continue
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=JST)
        except Exception:
            continue
        if (now - ts).total_seconds() < 86400:
            continue
        entry["date"] = ts.strftime("%Y-%m-%d")
        out.append(entry)
    return out


def main():
    force_all = "--all" in sys.argv

    from token_manager import check_and_refresh
    token = check_and_refresh()

    collected = set()
    if not force_all:
        collected = load_collected_ids() | load_collected_from_insights()

    # 1) Threads APIの実投稿を正とする
    targets = []
    try:
        targets = targets_from_api(token, collected)
    except Exception as e:
        logging.error(f"API起点の集計に失敗: {e}")
        print(f"[WARN] Threads APIからの取得に失敗しました（{e}）。post_logにフォールバックします")

    # 2) APIで拾えなかった分をpost_logで補う
    seen = {t["post_ids"][0] for t in targets}
    for entry in targets_from_log(collected):
        if entry["post_ids"][0] not in seen:
            targets.append(entry)

    if not targets:
        print("集計対象の投稿がありません（24時間未満または集計済み）")
        return

    print(f"集計対象: {len(targets)}件")

    by_date = {}
    for entry in targets:
        by_date.setdefault(entry["date"], []).append(entry)

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
