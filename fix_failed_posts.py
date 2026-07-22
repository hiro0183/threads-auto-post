"""
失敗したスロットのみ再生成する
"""
import json
from pathlib import Path
from content_generator import generate_thread

posts_dir = Path(__file__).parent / "posts"

fixed_total = 0

for f in sorted(posts_dir.glob("*.json")):
    data = json.loads(f.read_text(encoding="utf-8"))
    failed = [t for t, v in data.items() if not v or len(v) != 3]

    if not failed:
        continue

    print(f"\n{f.stem}: {len(failed)}件再生成")
    for slot in failed:
        print(f"  [{slot}] 再生成中...")
        try:
            posts = generate_thread()
            data[slot] = posts
            print(f"  [{slot}] OK")
            fixed_total += 1
        except Exception as e:
            print(f"  [{slot}] 失敗: {e}")

    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # txt も更新
    txt_file = f.with_suffix(".txt")
    lines = [f"# {f.stem} 投稿スケジュール\n"]
    for time_str, posts in sorted(data.items()):
        lines.append("=" * 40)
        lines.append(f"⏰ {time_str}")
        lines.append("=" * 40)
        if posts and len(posts) == 3:
            for j, post in enumerate(posts, 1):
                lines.append(f"【{j}投稿目】")
                lines.append(post)
                lines.append("")
        else:
            lines.append("※ 生成失敗")
            lines.append("")
    txt_file.write_text("\n".join(lines), encoding="utf-8")

print(f"\n合計 {fixed_total} スロットを修復しました")
