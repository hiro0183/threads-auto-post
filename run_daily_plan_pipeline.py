"""
毎晩の自動実行ジョブ: 翌日分をplanモードで生成→品質ゲートで判定→プレビュー出力、まで一気通貫で行う。
weekly_planがまだ置かれていない日は何もせず終了する（週次セッションが未実施でもエラーにしない）。

生成・判定はClaude Codeヘッドレス（Maxプラン枠内・API課金なし）で行う（2026-07-09変更）。

Windowsタスクスケジューラから毎晩21:30に実行する想定。
PCがオフで21:30を逃した場合はStartWhenAvailableで翌朝など次の起動時に追いかけ実行されるため、
「今日の分がまだ生成されていなければ今日の分も生成する」キャッチアップ処理を持つ。

使い方:
  python run_daily_plan_pipeline.py              # 今日分(未生成なら)＋翌日分
  python run_daily_plan_pipeline.py 2026-07-14   # 指定日のみ
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from generate_day import generate_day_from_plan, find_weekly_plan_for_date, POSTS_DIR
from quality_gate import run_gate
from export_preview import export as export_preview


def process_date(date_str: str) -> bool:
    if not find_weekly_plan_for_date(date_str):
        print(f"[スキップ] {date_str} を含むweekly_planがまだありません。週次セッション待ちです。")
        return False

    print(f"=== {date_str} 本文生成（planモード・サブスク実行） ===")
    schedule = generate_day_from_plan(date_str, preview=False)
    if not schedule:
        print(f"[エラー] {date_str} の生成に失敗しました")
        return False

    print(f"\n=== {date_str} 品質ゲート ===")
    gate_results = run_gate(date_str)

    print(f"\n=== {date_str} プレビュー出力 ===")
    export_preview(date_str, gate_results=gate_results)
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        targets = [args[0]]
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        targets = []
        # キャッチアップ: 前夜の実行を逃していて今日の分が無ければ、まず今日の分を作る
        # （投稿はRenderが5:00から順に読むため、途中からでも作る価値がある）
        if not (POSTS_DIR / f"{today}.json").exists() and find_weekly_plan_for_date(today):
            print(f"[キャッチアップ] {today} の投稿ファイルがありません。先に今日の分を生成します")
            targets.append(today)
        targets.append(tomorrow)

    for date_str in targets:
        process_date(date_str)

    # 司令室・オフィス画面も最新化（生成結果を反映）
    try:
        import ops_dashboard
        ops_dashboard.main()
    except Exception as e:
        print(f"[WARN] 司令室更新失敗: {e}")


if __name__ == "__main__":
    main()
