"""
翌日分の投稿を全件生成してファイルに保存する
使い方:
  python generate_daily_posts.py          # 翌日分を生成
  python generate_daily_posts.py --today  # 今日分を生成
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from content_generator import generate_thread, THEMES
import random

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"
POSTS_DIR.mkdir(exist_ok=True)

TIMES = [
    "05:45", "06:00", "07:00", "07:30", "08:00", "08:30",
    "09:00", "09:30", "10:00", "11:00", "12:00", "12:30",
    "13:00", "14:00", "15:00", "16:00", "17:00", "18:00",
    "18:30", "19:00", "19:15", "19:30", "20:00", "20:15",
    "20:20", "20:40", "21:00", "21:20", "21:40", "22:00",
]


def generate_and_save(target_date: datetime):
    filename = POSTS_DIR / f"{target_date.strftime('%Y-%m-%d')}.txt"
    themes = random.sample(THEMES, len(THEMES))
    # テーマが足りない場合はランダム補充
    while len(themes) < len(TIMES):
        themes.append(random.choice(THEMES))

    lines = []
    lines.append(f"# {target_date.strftime('%Y-%m-%d')} 投稿スケジュール（{len(TIMES)}件）\n")

    for i, time_str in enumerate(TIMES):
        print(f"[{i+1}/{len(TIMES)}] {time_str} 生成中...")
        try:
            posts = generate_thread(themes[i])
            lines.append(f"{'='*40}")
            lines.append(f"⏰ {time_str}")
            lines.append(f"{'='*40}")
            for j, post in enumerate(posts, 1):
                lines.append(f"【{j}投稿目】")
                lines.append(post)
                lines.append("")
        except Exception as e:
            print(f"  エラー: {e}")
            lines.append(f"{'='*40}")
            lines.append(f"⏰ {time_str}  ※生成失敗: {e}")
            lines.append("")

    content = "\n".join(lines)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n保存完了: {filename}")
    return filename


if __name__ == "__main__":
    if "--today" in sys.argv:
        target = datetime.now()
    else:
        target = datetime.now() + timedelta(days=1)

    print(f"{target.strftime('%Y-%m-%d')} 分の投稿を生成します（{len(TIMES)}件）\n")
    saved = generate_and_save(target)
    print(f"\n確認してください: {saved}")
