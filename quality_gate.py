"""
品質ゲート（生成とは独立したステップ）

本文生成（generate_day.py --plan）とは別のAPI呼び出しで、完成した投稿本文だけを渡して判定する。
生成側の会話履歴・プロンプトは一切共有しない（生成時の思い込みを引き継がせないため）。
NG時は本文のみ再生成（フックは変更しない）。同一スロットにつき最大2回まで判定し、
2回とも通らなければ自動修正を諦めて人間のプレビュー確認に回す（無限ループ防止）。

使い方:
  python quality_gate.py 2026-07-13
"""

import os
import sys
import json
from pathlib import Path

from dotenv import load_dotenv

from generate_day import find_weekly_plan_for_date
from content_generator import generate_body_from_hook, load_used_catches, claude_headless

load_dotenv()

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"
PROMPTS_DIR = BASE_DIR / "prompts"
GATE_RESULT_DIR = POSTS_DIR / "quality_gate"

MAX_JUDGE_ATTEMPTS = 2

GATE_PROMPT_TEMPLATE = """
あなたは投稿の品質チェック担当です。生成の経緯・意図は一切知らされていません。
以下のチェックリストと、許可されたペルソナ実数・読者像だけを根拠に、この投稿群がOKかNGかを判定してください。

{gate_rules}

【許可されたペルソナ実数・読者像（この数字・人物像以外の実績・数字が本文にあればNG）】
{persona}

【判定対象の投稿（1投稿目がフック）】
{posts_text}

以下の形式で必ず出力してください（判定行は必ず「判定: OK」または「判定: NG」で始めること）：
判定: OK または NG
理由: （NGの場合、上記チェックリストのどの項目に違反したか）
修正指示: （NGの場合、本文（2投稿目以降）をどう直すべきか。フックは変更しないこと）
"""


def load_gate_rules() -> str:
    path = PROMPTS_DIR / "gate.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_persona() -> str:
    path = PROMPTS_DIR / "persona.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def judge_posts(posts: list) -> dict:
    posts_text = "\n".join(f"{i+1}投稿目: {p}" for i, p in enumerate(posts))
    prompt = GATE_PROMPT_TEMPLATE.format(gate_rules=load_gate_rules(), persona=load_persona(), posts_text=posts_text)

    # 品質ゲートはHaiku・サブスク実行（API課金なし・2026-07-09変更）
    raw = claude_headless(prompt, model="haiku")
    first_line = raw.split("\n")[0]
    ok = "OK" in first_line and "NG" not in first_line
    return {"ok": ok, "raw": raw}


def run_gate(date_str: str):
    posts_file = POSTS_DIR / f"{date_str}.json"
    if not posts_file.exists():
        print(f"[エラー] {posts_file} が見つかりません")
        return None

    schedule = json.loads(posts_file.read_text(encoding="utf-8"))
    plan_found = find_weekly_plan_for_date(date_str)
    day_entries = plan_found[1] if plan_found else []
    entries_by_slot = {e.get("slot"): e for e in day_entries}

    results = {}
    changed = False

    for slot, posts in list(schedule.items()):
        current_posts = posts
        attempt = 0
        judgement = None

        while attempt < MAX_JUDGE_ATTEMPTS:
            judgement = judge_posts(current_posts)
            attempt += 1
            if judgement["ok"] or attempt >= MAX_JUDGE_ATTEMPTS:
                break

            entry = entries_by_slot.get(slot)
            if not entry:
                print(f"[{slot}] NG（weekly_planが見つからず再生成不可・人間確認へ）")
                break
            try:
                current_posts = generate_body_from_hook(
                    hook=entry.get("hook", ""),
                    type_label=entry.get("type", ""),
                    theme=entry.get("theme", ""),
                    conclusion=entry.get("conclusion", ""),
                    cta=entry.get("cta"),
                    three_posts=len(posts) >= 3,
                    used_catches=load_used_catches(days=7),
                )
                schedule[slot] = current_posts
                changed = True
            except Exception as e:
                print(f"[{slot}] 再生成エラー: {e}")
                break

        ok = bool(judgement and judgement["ok"])
        escalate = (not ok) and attempt >= MAX_JUDGE_ATTEMPTS
        results[slot] = {
            "ok": ok,
            "attempts": attempt,
            "escalate_to_human": escalate,
            "raw": judgement["raw"] if judgement else "",
        }
        status = "OK" if ok else ("要人間確認（2回NG）" if escalate else "NG")
        print(f"[{slot}] {status}")

    if changed:
        posts_file.write_text(json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n再生成分を反映して保存: {posts_file}")

    GATE_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    result_file = GATE_RESULT_DIR / f"{date_str}.json"
    result_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    n_ok = sum(1 for r in results.values() if r["ok"])
    n_escalate = sum(1 for r in results.values() if r["escalate_to_human"])
    print(f"\n判定結果保存: {result_file}")
    print(f"OK: {n_ok}件 / 要人間確認: {n_escalate}件 / 全体: {len(results)}件")
    return results


def main():
    if len(sys.argv) < 2:
        print("使い方: python quality_gate.py YYYY-MM-DD")
        return
    run_gate(sys.argv[1])


if __name__ == "__main__":
    main()
