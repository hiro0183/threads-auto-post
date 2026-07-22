"""
1日分の投稿（30件）を事前生成して posts/{date}.json に保存するスクリプト

使い方:
  python generate_day.py              # 翌日分を生成して保存
  python generate_day.py 2026-03-24  # 指定日を生成して保存
  python generate_day.py --preview   # 翌日分を生成して表示のみ（保存しない）
  python generate_day.py 2026-03-24 --preview
"""

import re
import sys
import json
import time
import random
from datetime import datetime, timedelta
from pathlib import Path

from post_runner import SLOT_PLAN
from content_generator import (
    generate_thread, generate_single_post, generate_body_from_hook,
    THEMES, AI_THEMES, PRIORITY_THEMES, load_used_catches,
)

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"
PROMPTS_DIR = BASE_DIR / "prompts"
WEEKLY_PLAN_DIR = POSTS_DIR / "weekly_plan"
MAX_CTA_PER_DAY = 3

NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
# 「1回」「3つ」のような素朴な計数語は対象外。金額・割合・実績を示す単位が付く数字のみをチェック対象にする
CLAIM_NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?(?=\s*(?:万円|万|円|%|％|倍|歳|ヶ月|時間))")


def _persona_numbers() -> set:
    """persona.mdに含まれる数値トークンの集合（許可リスト。単一情報源としてファイルから直接抽出）"""
    path = PROMPTS_DIR / "persona.md"
    if not path.exists():
        return set()
    return set(NUMBER_RE.findall(path.read_text(encoding="utf-8")))


def check_persona_numbers(posts: list) -> list:
    """本文（2投稿目以降）に実績・金額・割合の数字がペルソナ実数以外で使われていないか簡易照合。フック(1投稿目)はFable5承認済みのため対象外"""
    allowed = _persona_numbers()
    issues = []
    for i, post in enumerate(posts[1:], start=2):
        nums = CLAIM_NUMBER_RE.findall(post)
        suspicious = [n for n in nums if n not in allowed]
        if suspicious:
            issues.append(f"{i}投稿目に persona.md の実数と一致しない数字: {', '.join(suspicious)}（架空数字の可能性・要確認）")
    return issues

# 1日の投稿に占めるAI×経営テーマの割合（0.0〜1.0）。
# 0.4 = 約4割をAIネタにする。フォロワーの反応を見ながらこの数字だけ動かせばよい。
# 純経営に戻したいときは 0.0、AI全振りなら 1.0。
AI_RATIO = 0.0


def generate_day(date_str: str, preview: bool = False):
    tree_count = sum(1 for v in SLOT_PLAN.values() if v["type"] == "tree")
    single_count = sum(1 for v in SLOT_PLAN.values() if v["type"] == "single")
    cta_count = sum(1 for v in SLOT_PLAN.values() if v.get("cta"))
    total = len(SLOT_PLAN)

    print(f"\n{'[PREVIEW]' if preview else '[生成・保存]'} {date_str} 分（{total}スロット）\n")
    print(f"  構成: ツリー{tree_count}件 / 単体{single_count}件 / CTA付き{cta_count}件")
    print(f"  AI比率: {int(AI_RATIO*100)}%（約{round(total*AI_RATIO)}件をAI×経営テーマに割当）\n")
    print("=" * 60)

    # 過去7日の使用済みキャッチを読み込む（重複防止・短期）
    used_catches = load_used_catches(days=7)
    print(f"  重複防止: 過去7日の使用済みキャッチ {len(used_catches)}件を参照\n")

    schedule = {}

    # 経営プール（通常THEMES＋PRIORITY）とAIプールを分けて持つ
    biz_pool = THEMES.copy() + PRIORITY_THEMES.copy()
    ai_pool = AI_THEMES.copy()
    random.shuffle(biz_pool)
    random.shuffle(ai_pool)

    all_slots = sorted(SLOT_PLAN.keys())
    biz_idx = 0
    ai_idx = 0
    ai_acc = 0.0  # AI_RATIOに従ってAIテーマを1日に均等配置するためのアキュムレータ
    ai_used = 0

    for slot in all_slots:
        info = SLOT_PLAN[slot]

        # AI_RATIO分だけ均等にAIテーマを差し込む（連続クラスタを避ける）
        ai_acc += AI_RATIO
        if ai_acc >= 1.0 and ai_pool:
            ai_acc -= 1.0
            theme = ai_pool[ai_idx % len(ai_pool)]
            ai_idx += 1
            ai_used += 1
            slot_label = " [AI]"
        else:
            theme = biz_pool[biz_idx % len(biz_pool)]
            biz_idx += 1
            slot_label = ""

        label = "単体" if info["type"] == "single" else f"ツリー{'[CTA]' if info['cta'] else ''}"
        print(f"\n[{slot}]{slot_label} {label} テーマ:「{theme}」")

        try:
            if info["type"] == "single":
                posts = generate_single_post(theme=theme, used_catches=used_catches)
            else:
                posts = generate_thread(theme=theme, cta=info["cta"], used_catches=used_catches)

            for i, p in enumerate(posts, 1):
                label_p = f"投稿{i}" if len(posts) > 1 else "本文"
                print(f"  [{label_p}] {p[:60]}{'…' if len(p) > 60 else ''} ({len(p)}字)")

            schedule[slot] = posts
            # 生成したキャッチを当日の使用済みリストに追加（同日内重複防止）
            used_catches.append(posts[0][:60].replace("\n", " "))
            time.sleep(1.0)  # API負荷軽減

        except Exception as e:
            print(f"  [ERROR] {e}")
            continue

    print("\n" + "=" * 60)
    generated = len(schedule)
    print(f"\n生成完了: {generated}/{total} スロット")

    if not preview:
        POSTS_DIR.mkdir(exist_ok=True)
        out_path = POSTS_DIR / f"{date_str}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
        print(f"保存先: {out_path}")
    else:
        print("(プレビューモード: ファイルは保存しませんでした)")

    return schedule


def find_weekly_plan_for_date(date_str: str):
    """posts/weekly_plan/*.json を探索し、指定日を含むプランと当日分のスロット一覧を返す。無ければNone"""
    if not WEEKLY_PLAN_DIR.exists():
        return None
    for f in sorted(WEEKLY_PLAN_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        days = data.get("days") or {}
        if date_str in days:
            return data, days[date_str]
    return None


def verify_slot(entry: dict, posts: list, used_catches: list) -> list:
    """機械検証。問題があれば理由のリストを返す（空なら合格）"""
    issues = []
    hook = entry.get("hook", "")

    if not posts or posts[0] != hook:
        issues.append("フックが一字も変更されていない、という原則に違反（生成結果のフックが計画と不一致）")

    if len(posts) < 2:
        issues.append("単体投稿は禁止（ツリー2〜3投稿が必須・taboo.md #3）")

    hook_key = hook[:60].replace("\n", " ")
    if hook_key in used_catches:
        issues.append("直近7日以内に同一フックが使用済み（taboo.md #2の重複防止に抵触）")

    issues.extend(check_persona_numbers(posts))

    return issues


def generate_day_from_plan(date_str: str, preview: bool = False):
    """フェーズ3 planモード: weekly_planのフックを一字も変えず、本文（2〜3投稿目）のみ生成する"""
    found = find_weekly_plan_for_date(date_str)
    if not found:
        print(f"[エラー] {date_str} を含むweekly_planが見つかりません（posts/weekly_plan/*.jsonのdaysキーを確認してください）")
        return None

    plan, day_entries = found
    print(f"\n{'[PREVIEW]' if preview else '[生成・保存]'} {date_str} 分（planモード・{len(day_entries)}スロット）\n")
    if plan.get("directives"):
        print(f"  Fable5からの改善指示: {plan['directives']}\n")

    cta_today = sum(1 for e in day_entries if e.get("cta"))
    if cta_today > MAX_CTA_PER_DAY:
        print(f"[警告] この日のCTA本数が{cta_today}件でtaboo.md上限({MAX_CTA_PER_DAY}件)を超えています。weekly_planを確認してください\n")

    used_catches = load_used_catches(days=7)
    print(f"  重複防止: 過去7日の使用済みキャッチ {len(used_catches)}件を参照\n")
    print("=" * 60)

    schedule = {}
    ng_report = {}
    MAX_GEN_ATTEMPTS = 2

    for entry in day_entries:
        slot = entry.get("slot")
        if not slot:
            continue
        print(f"\n[{slot}] 型:{entry.get('type','')} テーマ:「{entry.get('theme','')}」")
        print(f"  フック（固定）: {entry.get('hook','')}")

        posts = None
        issues = ["未試行"]
        last_error = None

        for attempt in range(1, MAX_GEN_ATTEMPTS + 1):
            try:
                posts = generate_body_from_hook(
                    hook=entry.get("hook", ""),
                    type_label=entry.get("type", ""),
                    theme=entry.get("theme", ""),
                    conclusion=entry.get("conclusion", ""),
                    cta=entry.get("cta"),
                    three_posts=True,
                    used_catches=used_catches,
                )
            except Exception as e:
                last_error = e
                print(f"  [ERROR] 生成失敗（{attempt}回目）: {e}")
                if attempt < MAX_GEN_ATTEMPTS:
                    continue
                issues = [f"生成エラー: {e}"]
                posts = None
                break

            issues = verify_slot(entry, posts, used_catches)
            if not issues:
                break
            print(f"  [NG（{attempt}回目）] {'; '.join(issues)}")
            if attempt < MAX_GEN_ATTEMPTS:
                print("  → 本文のみ再生成")

        if posts is None:
            print(f"  → 生成不能。人間確認へ回します")
            ng_report[slot] = issues
            continue

        if issues:
            print(f"  [NG確定] {'; '.join(issues)} → 人間確認へ回します（このスロットは生成結果を保存しつつ要確認扱い）")
            ng_report[slot] = issues

        for i, p in enumerate(posts, 1):
            print(f"  [投稿{i}] {p[:60]}{'…' if len(p) > 60 else ''} ({len(p)}字)")

        schedule[slot] = posts
        used_catches.append(posts[0][:60].replace("\n", " "))
        time.sleep(1.0)

    print("\n" + "=" * 60)
    print(f"\n生成完了: {len(schedule)}/{len(day_entries)} スロット（要人間確認: {len(ng_report)}件）")

    if not preview:
        POSTS_DIR.mkdir(exist_ok=True)
        out_path = POSTS_DIR / f"{date_str}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
        print(f"保存先: {out_path}")

        if ng_report:
            ng_path = POSTS_DIR / f"{date_str}_要確認.json"
            with open(ng_path, "w", encoding="utf-8") as f:
                json.dump(ng_report, f, ensure_ascii=False, indent=2)
            print(f"要人間確認レポート: {ng_path}")
    else:
        print("(プレビューモード: ファイルは保存しませんでした)")

    return schedule


def main():
    args = sys.argv[1:]
    preview = "--preview" in args
    plan_mode = "--plan" in args
    date_args = [a for a in args if not a.startswith("--")]

    if date_args:
        date_str = date_args[0]
    else:
        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")

    if plan_mode:
        generate_day_from_plan(date_str, preview=preview)
    else:
        generate_day(date_str, preview=preview)


if __name__ == "__main__":
    main()
