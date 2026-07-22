"""
独立検品（2026-07-18新設）

日次生成がclaude.aiクラウドルーティン（自己チェックのみ）に移ったことで失われた
「生成と別呼び出しの独立品質ゲート」（2026-07-07設計）をローカル実行で復元する。

- **昼12:00（Threads_NoonInspection）: 明日分を検品** ← 主役。NGが出ても
  午後〜夜にゆっくり直せる（ヒロさん案・2026-07-18採用）
- 朝04:45（Threads_MorningInspection）: 今日分の最終確認
- 検品対象は posts/{date}.json、判定は Haiku（サブスク実行・API課金なし）
- **非ブロック**: NGでも原稿は書き換えない・投稿も止めない。
  結果を posts/quality_gate/{date}_inspection.json に保存し、
  司令室（ops_dashboard.py）が読んで赤表示＋「今日やること」に載せるだけ

使い方:
  python morning_inspection.py              # 今日分
  python morning_inspection.py tomorrow     # 明日分（昼の便）
  python morning_inspection.py 2026-07-19   # 指定日
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from quality_gate import judge_posts, GATE_RESULT_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"


def inspect(date_str: str):
    posts_file = POSTS_DIR / f"{date_str}.json"
    if not posts_file.exists():
        print(f"[スキップ] {posts_file} がありません（鮮度チェック側が検知します）")
        return None

    schedule = json.loads(posts_file.read_text(encoding="utf-8"))
    results = {}
    for slot, posts in schedule.items():
        if not posts:  # 休止スロット
            continue
        try:
            j = judge_posts(posts)
        except Exception as e:
            j = {"ok": False, "raw": f"検品実行エラー: {e}"}
        results[slot] = {"ok": j["ok"], "raw": j["raw"]}
        print(f"[{slot}] {'OK' if j['ok'] else 'NG'}")

    GATE_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out = GATE_RESULT_DIR / f"{date_str}_inspection.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_ng = sum(1 for r in results.values() if not r["ok"])
    print(f"\n検品結果保存: {out}")
    print(f"合格: {len(results) - n_ng}/{len(results)}スロット")
    return results


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg == "tomorrow":
        date_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    elif arg:
        date_str = arg
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
    inspect(date_str)

    # 検品結果をすぐ司令室に反映（昼の便でNGが出たらその場で見えるように）
    try:
        import ops_dashboard
        ops_dashboard.main()
    except Exception as e:
        print(f"[WARN] 司令室更新失敗: {e}")


if __name__ == "__main__":
    main()
