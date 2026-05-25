"""
1日分の投稿（30件）を事前生成して posts/{date}.json に保存するスクリプト

使い方:
  python generate_day.py              # 翌日分を生成して保存
  python generate_day.py 2026-03-24  # 指定日を生成して保存
  python generate_day.py --preview   # 翌日分を生成して表示のみ（保存しない）
  python generate_day.py 2026-03-24 --preview
"""

import sys
import json
import time
import random
from datetime import datetime, timedelta
from pathlib import Path

from post_runner import SLOT_PLAN
from content_generator import generate_thread, generate_single_post, THEMES, PRIORITY_THEMES, load_used_catches

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"


def generate_day(date_str: str, preview: bool = False):
    tree_count = sum(1 for v in SLOT_PLAN.values() if v["type"] == "tree")
    single_count = sum(1 for v in SLOT_PLAN.values() if v["type"] == "single")
    cta_count = sum(1 for v in SLOT_PLAN.values() if v.get("cta"))
    total = len(SLOT_PLAN)

    print(f"\n{'[PREVIEW]' if preview else '[生成・保存]'} {date_str} 分（{total}スロット）\n")
    print(f"  構成: ツリー{tree_count}件 / 単体{single_count}件 / CTA付き{cta_count}件\n")
    print("=" * 60)

    # 過去7日の使用済みキャッチを読み込む（重複防止・短期）
    used_catches = load_used_catches(days=7)
    print(f"  重複防止: 過去7日の使用済みキャッチ {len(used_catches)}件を参照\n")

    schedule = {}

    # PRIORITY_THEMES を通常 THEMES に混ぜ込み、強制配置をやめて多様性確保
    themes_pool = THEMES.copy() + PRIORITY_THEMES.copy()
    random.shuffle(themes_pool)

    all_slots = sorted(SLOT_PLAN.keys())
    theme_idx = 0

    for slot in all_slots:
        info = SLOT_PLAN[slot]

        theme = themes_pool[theme_idx % len(themes_pool)]
        theme_idx += 1
        slot_label = ""

        label = "単体" if info["type"] == "single" else f"ツリー{'[CTA]' if info['cta'] else ''}"
        print(f"\n[{slot}]{slot_label} {label} テーマ:「{theme}」")

        try:
            if info["type"] == "single":
                posts = generate_single_post(theme=theme, used_catches=used_catches)
            else:
                posts = generate_thread(theme=theme, cta=info["cta"], used_catches=used_catches)

            for i, p in enumerate(posts, 1):
                label_p = f"投稿{i}" if len(posts) > 1 else "本文"
                print(f"  [{label_p}] {p[:60]}{'…' if len(p) > 60 else ''} ({len(p)}字)")

            schedule[slot] = posts
            # 生成したキャッチを当日の使用済みリストに追加（同日内重複防止）
            used_catches.append(posts[0][:60].replace("\n", " "))
            time.sleep(1.0)  # API負荷軽減

        except Exception as e:
            print(f"  [ERROR] {e}")
            continue

    print("\n" + "=" * 60)
    generated = len(schedule)
    print(f"\n生成完了: {generated}/{total} スロット")

    if not preview:
        POSTS_DIR.mkdir(exist_ok=True)
        out_path = POSTS_DIR / f"{date_str}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
        print(f"保存先: {out_path}")
    else:
        print("(プレビューモード: ファイルは保存しませんでした)")

    return schedule


def main():
    args = sys.argv[1:]
    preview = "--preview" in args
    date_args = [a for a in args if not a.startswith("--")]

    if date_args:
        date_str = date_args[0]
    else:
        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")

    generate_day(date_str, preview=preview)


if __name__ == "__main__":
    main()
