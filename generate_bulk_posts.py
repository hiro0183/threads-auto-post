"""
複数日分の投稿をまとめて生成する
使い方:
  python generate_bulk_posts.py 10   # 明日から10日分
  python generate_bulk_posts.py 7    # 明日から7日分
"""

import sys
from datetime import datetime, timedelta
from generate_daily_posts import generate_and_save, TIMES

days = int(sys.argv[1]) if len(sys.argv) > 1 else 10

print(f"明日から{days}日分の投稿を生成します（各{len(TIMES)}件）\n")

for i in range(1, days + 1):
    target = datetime.now() + timedelta(days=i)
    print(f"\n{'='*50}")
    print(f"【{i}/{days}日目】{target.strftime('%Y-%m-%d')} 生成開始")
    print(f"{'='*50}")
    generate_and_save(target)

print(f"\n全{days}日分の生成完了！")
print(f"保存先: C:\\Users\\tujid\\threads_tool\\posts\\")
