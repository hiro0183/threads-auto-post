"""
指定期間分の投稿を一括生成してExcelを更新するスクリプト

使い方:
  python generate_range.py 2026-04-03 2026-04-28
"""

import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent


def main():
    if len(sys.argv) < 3:
        print("使い方: python generate_range.py 開始日 終了日")
        print("例: python generate_range.py 2026-04-03 2026-04-28")
        sys.exit(1)

    start = datetime.strptime(sys.argv[1], "%Y-%m-%d")
    end   = datetime.strptime(sys.argv[2], "%Y-%m-%d")

    days = (end - start).days + 1
    print(f"\n一括生成開始: {sys.argv[1]} ~ {sys.argv[2]} ({days}日分)")
    print("=" * 60)

    success = []
    failed  = []

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        json_path = BASE_DIR / "posts" / f"{date_str}.json"

        # すでに生成済みならスキップ
        if json_path.exists():
            print(f"\n[SKIP] {date_str} は生成済み")
            success.append(date_str)
            current += timedelta(days=1)
            continue

        print(f"\n[{len(success)+len(failed)+1}/{days}] {date_str} 生成中...")
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "generate_day.py"), date_str],
            capture_output=False,
        )
        if result.returncode == 0:
            success.append(date_str)
        else:
            print(f"  [ERROR] {date_str} の生成に失敗")
            failed.append(date_str)

        current += timedelta(days=1)

    print("\n" + "=" * 60)
    print(f"\n生成完了: {len(success)}日成功 / {len(failed)}日失敗")
    if failed:
        print(f"失敗日: {', '.join(failed)}")

    # Excelを更新
    print("\nExcelシートを更新中...")
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "export_excel.py"), "2026-03-30", "30"],
        capture_output=False,
    )
    if result.returncode == 0:
        print("Excelの更新が完了しました")
    else:
        print("[ERROR] Excel更新に失敗しました。手動で python export_excel.py を実行してください")


if __name__ == "__main__":
    main()
