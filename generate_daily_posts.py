"""
翌日分の投稿を全件生成してファイルに保存する
使い方:
  python generate_daily_posts.py          # 翌日分を生成
  python generate_daily_posts.py --today  # 今日分を生成
"""

import sys
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from content_generator import generate_thread, generate_single_post, THEMES

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

# post_runner.py の SLOT_PLAN と同期させること
SLOT_PLAN = {
    "05:45": {"type": "tree",   "cta": False},
    "06:00": {"type": "single", "cta": False},
    "07:00": {"type": "tree",   "cta": False},
    "07:30": {"type": "tree",   "cta": False},
    "08:00": {"type": "tree",   "cta": True},
    "08:30": {"type": "single", "cta": False},
    "09:00": {"type": "tree",   "cta": False},
    "09:30": {"type": "tree",   "cta": False},
    "10:00": {"type": "tree",   "cta": True},
    "11:00": {"type": "single", "cta": False},
    "12:00": {"type": "tree",   "cta": False},
    "12:30": {"type": "tree",   "cta": True},
    "13:00": {"type": "tree",   "cta": False},
    "14:00": {"type": "single", "cta": False},
    "15:00": {"type": "tree",   "cta": False},
    "16:00": {"type": "tree",   "cta": True},
    "17:00": {"type": "tree",   "cta": True},
    "18:00": {"type": "tree",   "cta": False},
    "18:30": {"type": "single", "cta": False},
    "19:00": {"type": "tree",   "cta": True},
    "19:15": {"type": "tree",   "cta": False},
    "19:30": {"type": "tree",   "cta": False},
    "20:00": {"type": "single", "cta": False},
    "20:15": {"type": "tree",   "cta": False},
    "20:20": {"type": "tree",   "cta": True},
    "20:40": {"type": "single", "cta": False},
    "21:00": {"type": "tree",   "cta": False},
    "21:20": {"type": "tree",   "cta": True},
    "21:40": {"type": "tree",   "cta": False},
    "22:00": {"type": "single", "cta": False},
}


def generate_and_save(target_date: datetime):
    date_str = target_date.strftime('%Y-%m-%d')
    json_file = POSTS_DIR / f"{date_str}.json"
    txt_file  = POSTS_DIR / f"{date_str}.txt"

    themes = random.sample(THEMES, len(THEMES))
    while len(themes) < len(TIMES):
        themes.append(random.choice(THEMES))

    # treeスロットの約3割（9件）をランダムに「X選」スタイルにする
    tree_indices = [i for i, t in enumerate(TIMES) if SLOT_PLAN.get(t, {}).get("type") == "tree"]
    list_style_indices = set(random.sample(tree_indices, k=round(len(tree_indices) * 0.3)))

    schedule = {}   # JSONデータ: {"05:45": ["投稿1", "投稿2", "投稿3"], ...}
    txt_lines = [f"# {date_str} 投稿スケジュール（{len(TIMES)}件）\n"]

    for i, time_str in enumerate(TIMES):
        slot_info = SLOT_PLAN.get(time_str, {"type": "tree", "cta": False})
        is_single = slot_info["type"] == "single"
        use_list = i in list_style_indices  # treeスロットのみ該当
        cta = slot_info["cta"]

        style_label = " [単体]" if is_single else (" [X選型]" if use_list else "")
        print(f"[{i+1}/{len(TIMES)}] {time_str} 生成中...{style_label}")
        try:
            if is_single:
                posts = generate_single_post(themes[i])
            else:
                posts = generate_thread(themes[i], cta=cta, list_style=use_list)
            schedule[time_str] = posts

            txt_lines.append(f"{'='*40}")
            txt_lines.append(f"⏰ {time_str}")
            txt_lines.append(f"{'='*40}")
            for j, post in enumerate(posts, 1):
                txt_lines.append(f"【{j}投稿目】")
                txt_lines.append(post)
                txt_lines.append("")
        except Exception as e:
            print(f"  エラー: {e}")
            schedule[time_str] = None
            txt_lines.append(f"{'='*40}")
            txt_lines.append(f"⏰ {time_str}  ※生成失敗: {e}")
            txt_lines.append("")

    # JSON保存（GitHub Actions用）
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

    # TXT保存（人間確認用）
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    print(f"\n保存完了: {txt_file}")
    return txt_file


if __name__ == "__main__":
    if "--today" in sys.argv:
        target = datetime.now()
    else:
        target = datetime.now() + timedelta(days=1)

    print(f"{target.strftime('%Y-%m-%d')} 分の投稿を生成します（{len(TIMES)}件）\n")
    saved = generate_and_save(target)
    print(f"\n確認してください: {saved}")
