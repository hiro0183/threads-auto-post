"""
デスクトップの「Threads投稿プレビュー」フォルダの .txt を編集後、
posts/{date}.json に反映するスクリプト

使い方:
  python import_preview.py              # プレビューフォルダの全txtを反映
  python import_preview.py 2026-03-24  # 指定日のみ反映
"""

import sys
import re
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"
DESKTOP = Path.home() / "OneDrive" / "Desktop" / "コンサル投稿確認"


def parse_txt(txt_path: Path) -> dict:
    text = txt_path.read_text(encoding="utf-8")
    schedule = {}

    # 【HH:MM】で各スロットのブロックに分割
    blocks = re.split(r"\n(?=【\d{2}:\d{2}】)", text)

    for block in blocks:
        # 時刻を取得
        time_match = re.match(r"【(\d{2}:\d{2})】", block)
        if not time_match:
            continue
        slot = time_match.group(1)

        # ヘッダー行と区切り線を除去
        body = re.sub(r"^【\d{2}:\d{2}】.*\n", "", block)
        body = re.sub(r"^-{3,}.*\n", "", body, flags=re.MULTILINE)
        body = body.strip()

        if not body:
            continue

        # ツリー（▼ N投稿目 で分割）か単体か判定
        if "▼ 1投稿目" in body:
            posts = []
            parts = re.split(r"▼ \d+投稿目\n?", body)
            for part in parts:
                part = part.strip()
                if part:
                    posts.append(part)
            schedule[slot] = posts
        else:
            # 単体投稿
            schedule[slot] = [body]

    return schedule


def import_file(date_str: str):
    txt_file = DESKTOP / f"{date_str}.txt"
    if not txt_file.exists():
        print(f"[スキップ] {date_str}.txt が見つかりません: {txt_file}")
        return

    schedule = parse_txt(txt_file)
    if not schedule:
        print(f"[エラー] {date_str}.txt のパースに失敗しました")
        return

    POSTS_DIR.mkdir(exist_ok=True)
    out_file = POSTS_DIR / f"{date_str}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

    print(f"反映完了: {date_str}.txt → {out_file}（{len(schedule)}スロット）")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        for date_str in args:
            import_file(date_str)
    else:
        txt_files = sorted(DESKTOP.glob("*.txt"))
        if not txt_files:
            print("プレビューフォルダに .txt ファイルがありません")
            return
        for f in txt_files:
            import_file(f.stem)


if __name__ == "__main__":
    main()
