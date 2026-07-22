"""
月曜の空白埋め（2026-07-18新設）

日次生成（claude.aiクラウド・毎朝06:00）は「前日に翌日分」を作るが、
週次プランは月曜05:10にできるため、日曜06:00時点では月曜分が作れない。
→ 毎週月曜の朝、週次プラン確定後にこのスクリプトが当日分を生成してpushする。

- タスクスケジューラ（Threads_MondayCatchup）から月曜06:30に実行
  （週次セッションが長引く場合に備え、30分おきに数回リトライされる想定）
- 冪等: 当日分が既に「週次プラン以降のコミット」なら何もせず終了
- weekly_planがまだ無ければ何もせず終了（次のリトライを待つ）

使い方:
  python monday_catchup.py              # 今日分
  python monday_catchup.py 2026-07-20   # 指定日（テスト用）
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")

    from ops_dashboard import posts_freshness, _weekly_plan_for
    from run_daily_plan_pipeline import process_date

    if _weekly_plan_for(date_str) is None:
        print(f"[待機] {date_str} を含むweekly_planがまだありません（週次セッション実行中の可能性・次のリトライで再確認）")
        return

    ok, detail, _kind = posts_freshness(date_str)
    if ok:
        print(f"[完了済み] {detail}")
        return

    print(f"[生成開始] {date_str}: {detail}")
    if not process_date(date_str):
        print(f"[エラー] {date_str} の生成に失敗しました（次のリトライで再挑戦）")
        sys.exit(1)

    # posts配下だけをpush（無関係な作業中ファイルを巻き込まない）
    subprocess.run(["git", "add", f"posts/{date_str}.json", "posts/quality_gate"], cwd=BASE_DIR, check=True)
    r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=BASE_DIR)
    if r.returncode == 0:
        print("[スキップ] コミットする変更がありません")
        return
    subprocess.run(["git", "commit", "-m", f"月曜キャッチアップ: {date_str} 当日分生成（週次プラン確定後）"], cwd=BASE_DIR, check=True)
    subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
    print(f"[完了] {date_str} を生成してpushしました（Renderが残りスロットから新原稿で投稿）")


if __name__ == "__main__":
    main()
