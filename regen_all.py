"""
3/23〜4/2 の11日分を全て再生成する
"""
from datetime import datetime, timedelta
from generate_daily_posts import generate_and_save, TIMES

dates = [datetime(2026, 3, 23) + timedelta(days=i) for i in range(11)]

print(f"{len(dates)}日分の投稿を再生成します（各{len(TIMES)}件）\n")

for i, target in enumerate(dates, 1):
    print(f"\n{'='*50}")
    print(f"【{i}/{len(dates)}日目】{target.strftime('%Y-%m-%d')} 生成開始")
    print(f"{'='*50}")
    generate_and_save(target)

print(f"\n全{len(dates)}日分の再生成完了！")
