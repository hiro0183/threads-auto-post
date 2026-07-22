"""
投稿済みの内容をObsidianの投稿履歴フォルダに自動保存するスクリプト

使い方:
  python save_posts_to_obsidian.py           # 未保存の投稿をすべて保存
  python save_posts_to_obsidian.py --all     # 全日付を再生成（上書き）
  python save_posts_to_obsidian.py --date 2026-03-30  # 指定日のみ再生成
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "post_log.jsonl"
SAVED_FILE = BASE_DIR / "posts_obsidian_saved.jsonl"
OBSIDIAN_HISTORY_DIR = Path(r"C:\Users\tujid\OneDrive\Desktop\HIRAYASU\コンサルThreads\投稿履歴")

JST = timezone(timedelta(hours=9))


def load_saved_ids() -> set:
    if not SAVED_FILE.exists():
        return set()
    ids = set()
    for line in SAVED_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            try:
                ids.add(json.loads(line)["root_post_id"])
            except Exception:
                pass
    return ids


def mark_saved(root_post_id: str, date_str: str):
    with open(SAVED_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"root_post_id": root_post_id, "date": date_str}) + "\n")


def build_markdown(date_str: str, entries: list) -> str:
    lines = [f"# {date_str} 投稿履歴\n"]

    for entry in sorted(entries, key=lambda x: x.get("slot", "")):
        slot = entry.get("slot", "??:??")
        posts = entry.get("posts", [])
        post_type = entry.get("post_type", "tree")

        lines.append(f"## {slot}\n")

        if post_type == "single" or len(posts) == 1:
            lines.append(posts[0] if posts else "")
            lines.append("")
            lines.append("---\n")
        else:
            for post in posts:
                lines.append(post)
                lines.append("")
                lines.append("---\n")

    return "\n".join(lines)


def save_date(date_str: str, entries: list):
    OBSIDIAN_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    md_file = OBSIDIAN_HISTORY_DIR / f"{date_str}.md"
    md_file.write_text(build_markdown(date_str, entries), encoding="utf-8")
    print(f"保存: {md_file} ({len(entries)}件)")


def main():
    force_all = "--all" in sys.argv
    target_date = None
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        if idx + 1 < len(sys.argv):
            target_date = sys.argv[idx + 1]

    if not LOG_FILE.exists():
        print("投稿ログがありません")
        return

    saved_ids = set() if force_all else load_saved_ids()

    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass

    # 対象フィルタ
    targets = []
    for entry in entries:
        if entry.get("status") != "ok":
            continue
        if not entry.get("post_ids"):
            continue
        root_id = entry["post_ids"][0]
        if root_id in saved_ids:
            continue
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=JST)
        except Exception:
            continue
        date_str = ts.strftime("%Y-%m-%d")
        if target_date and date_str != target_date:
            continue
        targets.append((date_str, entry))

    if not targets:
        print("保存対象の投稿がありません（全件保存済み）")
        return

    print(f"保存対象: {len(targets)}件")

    # 日付ごとにグループ化
    by_date: dict[str, list] = {}
    for date_str, entry in targets:
        by_date.setdefault(date_str, []).append(entry)

    for date_str, day_entries in sorted(by_date.items()):
        # 既存ファイルがある場合はマージ（既存 + 新規を合算）
        md_file = OBSIDIAN_HISTORY_DIR / f"{date_str}.md"
        if md_file.exists() and not force_all and not target_date:
            # 既存の投稿IDを確認して重複除去（再保存でなければスキップ）
            pass

        save_date(date_str, day_entries)

        if not force_all:
            for entry in day_entries:
                mark_saved(entry["post_ids"][0], date_str)

    print("完了")


if __name__ == "__main__":
    main()
