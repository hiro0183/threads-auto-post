"""
【コンサル垢 専用】
posts/{date}.json を読み込んで、デスクトップの「コンサル投稿確認」フォルダに
読みやすいテキストファイルとして書き出すスクリプト

※ ラポール整体院（@rapport.sango）側とは別物。混同しないこと。

使い方:
  python export_preview.py              # posts/ 内の全JSONを書き出し
  python export_preview.py tomorrow    # git pull + 明日分と今日分を書き出し（毎朝06:25のタスク用）
  python export_preview.py 2026-03-24  # 指定日のみ書き出し
"""

import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"
DESKTOP = Path.home() / "OneDrive" / "Desktop" / "コンサル投稿確認"

SLOT_TYPES = {
    "05:00": "ツリー",     "05:15": "単体",
    "05:30": "ツリー",     "05:45": "ツリー",
    "06:00": "単体",       "06:30": "ツリー",
    "07:00": "ツリー",     "07:30": "ツリー",
    "08:00": "ツリー★CTA", "08:30": "単体",
    "09:00": "ツリー",     "09:30": "ツリー",
    "09:45": "単体",       "10:00": "ツリー★CTA",
    "10:15": "ツリー",     "10:30": "単体",
    "11:00": "ツリー",     "11:30": "ツリー",
    "12:00": "ツリー★CTA", "12:30": "ツリー",
    "12:45": "単体",       "13:00": "ツリー",
    "13:15": "ツリー",     "13:30": "単体",
    "14:00": "ツリー",     "14:30": "ツリー",
    "15:00": "ツリー★CTA", "15:30": "単体",
    "16:00": "ツリー",     "16:30": "ツリー",
    "16:45": "単体",       "17:00": "ツリー★CTA",
    "17:30": "ツリー",     "18:00": "ツリー",
    "18:15": "単体",       "18:30": "ツリー",
    "18:45": "ツリー★CTA", "19:00": "ツリー",
    "19:15": "単体",       "19:30": "ツリー",
    "19:45": "ツリー",     "20:00": "単体",
    "20:15": "ツリー",     "20:20": "ツリー★CTA",
    "20:40": "単体",       "21:00": "ツリー",
    "21:20": "ツリー★CTA", "21:40": "ツリー",
    "21:50": "単体",       "22:00": "ツリー",
}


def export(date_str: str, gate_results: dict = None):
    json_file = POSTS_DIR / f"{date_str}.json"
    if not json_file.exists():
        print(f"[スキップ] {date_str}.json が見つかりません")
        return

    with open(json_file, encoding="utf-8") as f:
        schedule = json.load(f)

    gate_file = POSTS_DIR / "quality_gate" / f"{date_str}.json"
    if gate_results is None and gate_file.exists():
        try:
            gate_results = json.loads(gate_file.read_text(encoding="utf-8"))
        except Exception:
            gate_results = None

    DESKTOP.mkdir(parents=True, exist_ok=True)
    out_file = DESKTOP / f"{date_str}.txt"

    n_trees = sum(1 for v in schedule.values() if isinstance(v, list) and len(v) >= 2)
    n_posts = sum(len(v) for v in schedule.values() if isinstance(v, list))
    lines = []
    lines.append(f"{'='*50}")
    lines.append(f"  {date_str}  投稿一覧（{n_trees}ツリー・実投稿{n_posts}本）")
    if gate_results:
        n_ok = sum(1 for r in gate_results.values() if r.get("ok"))
        n_escalate = sum(1 for r in gate_results.values() if r.get("escalate_to_human"))
        lines.append(f"  品質ゲート: OK {n_ok}件 / 要確認 {n_escalate}件")
    lines.append(f"{'='*50}\n")

    for slot, posts in sorted(schedule.items()):
        kind = SLOT_TYPES.get(slot, "")
        gate_note = ""
        if gate_results and slot in gate_results:
            r = gate_results[slot]
            if r.get("ok"):
                gate_note = "  [品質ゲートOK]"
            elif r.get("escalate_to_human"):
                gate_note = "  [⚠️品質ゲート要確認]"
            else:
                gate_note = "  [品質ゲートNG→再生成済み]"
        lines.append(f"【{slot}】{kind}{gate_note}")
        lines.append("-" * 40)

        if len(posts) == 1:
            lines.append(posts[0])
        else:
            for i, p in enumerate(posts, 1):
                lines.append(f"▼ {i}投稿目")
                lines.append(p)
                if i < len(posts):
                    lines.append("")

        if gate_results and slot in gate_results and gate_results[slot].get("escalate_to_human"):
            lines.append("")
            lines.append(f"  → 品質ゲート判定理由: {gate_results[slot].get('raw', '')[:300]}")

        lines.append("")

    out_file.write_text("\n".join(lines), encoding="utf-8-sig")
    print(f"保存完了: {out_file}")


def sync_repo():
    """原稿はクラウド生成→GitHub pushなので、書き出す前にpullして最新化する"""
    try:
        r = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            last = (r.stdout or "").strip().splitlines()
            print(f"[sync] git pull: {last[-1] if last else 'ok'}")
        else:
            print(f"[WARN] git pull失敗（ローカルの原稿で続行）: {(r.stderr or '')[:200]}")
    except Exception as e:
        print(f"[WARN] git pull実行エラー（ローカルの原稿で続行）: {e}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args and args[0] == "tomorrow":
        sync_repo()
        export(datetime.now().strftime("%Y-%m-%d"))
        export((datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))
    elif args:
        for date_str in args:
            export(date_str)
    else:
        json_files = sorted(POSTS_DIR.glob("*.json"))
        if not json_files:
            print("posts/ フォルダにJSONファイルがありません")
            return
        for f in json_files:
            export(f.stem)


if __name__ == "__main__":
    main()
