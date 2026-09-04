"""リサーチ部門の出力を1枚にまとめる（2026-09-05新設・AIを呼ばない・費用ゼロ）。

背景:
  なりあいさんの整理する4要素（①アカウント設計 ②投稿のリサーチ ③投稿のテンプレ ④投稿分析）の
  うち、**②リサーチだけが仕組みとして存在しなかった**。競合も読者の質問も題材の棚も、
  集める担当がいなかった。ここがリサーチ部門の実体。

  週次企画（日曜）と日次執筆（毎朝）が、これ1枚を読めば材料がそろう状態にする。

中身は4つ:
  1. 今週の題材候補 — `prompts/theme_shelf.md`（小川さんの脳みそ180題材）から輪番で出す。
     過去に出した分は後回しにするので、毎週同じ題材に戻らない。
  2. 読者の声 — `collect_replies.py` が集めた読者の返信。
  3. 直近14日で使ったテーマ — 重複回避の材料（weekly_plan の theme ラベル）。
  4. 本文の骨格の偏り — `check_body_style.py` の集計。どの型に寄っているか。

使い方:
    python research_digest.py             # 生成して prompts/research_digest.md に保存
    python research_digest.py --print     # 保存せず表示するだけ
    python research_digest.py --n 24      # 題材候補の本数を変える（既定20）
"""
import io
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROMPTS = BASE / "prompts"
POSTS = BASE / "posts"
PLAN_DIR = POSTS / "weekly_plan"
STATE = BASE / "state" / "theme_shelf_offered.json"
OUT = PROMPTS / "research_digest.md"
REPLIES = BASE / "replies_collected.jsonl"

SHELF_ITEM = re.compile(r"^- \*\*(.+?)\*\*(?: — (.*))?$")


def load_shelf() -> list:
    """theme_shelf.md から (カテゴリ, 見出し, 要点) を読む"""
    f = PROMPTS / "theme_shelf.md"
    if not f.exists():
        return []
    items, cat = [], ""
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cat = line[3:].strip()
        m = SHELF_ITEM.match(line.strip())
        if m and cat:
            items.append((cat, m.group(1), (m.group(2) or "").strip()))
    return items


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def pick_themes(shelf: list, n: int) -> list:
    """出した回数が少ない順に、かつカテゴリを跨いで散らして n 件返す。

    素直に「出した回数が少ない順」だけで並べると、初回は全件count=0のため
    棚の先頭カテゴリ（01_AIマーケティング戦略）だけで埋まってしまう。
    AI×経営テーマは実測で平均views最下位（AI_RATIO=0.0に変更済み）なので、
    そこに偏るのは実害がある。カテゴリごとに輪番で1件ずつ取る。
    """
    st = load_state()
    by_cat = {}
    for cat, title, point in shelf:
        rec = st.get(title) or {}
        by_cat.setdefault(cat, []).append(
            ((rec.get("count", 0), rec.get("last", "")), (cat, title, point))
        )
    for cat in by_cat:
        by_cat[cat].sort(key=lambda x: x[0])

    picked, cats = [], sorted(by_cat)
    round_i = 0
    while len(picked) < n:
        added = False
        for cat in cats:
            if round_i < len(by_cat[cat]):
                picked.append(by_cat[cat][round_i][1])
                added = True
                if len(picked) >= n:
                    break
        if not added:
            break
        round_i += 1
    return picked


def remember(picked: list):
    st = load_state()
    today = date.today().isoformat()
    for _, title, _ in picked:
        rec = st.get(title) or {"count": 0}
        rec["count"] = rec.get("count", 0) + 1
        rec["last"] = today
        st[title] = rec
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def recent_reader_voices(days: int = 30) -> list:
    if not REPLIES.exists():
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    out = []
    for line in REPLIES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if (d.get("post_date") or "") >= cutoff:
            out.append(d)
    return out


def used_themes(days: int = 14) -> Counter:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    c = Counter()
    for f in sorted(PLAN_DIR.glob("*.json")):
        try:
            plan = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for d, entries in (plan.get("days") or {}).items():
            if d < cutoff:
                continue
            for e in entries:
                t = (e.get("theme") or "").strip()
                if t:
                    c[t] += 1
    return c


def skeleton_bias(days: int = 14) -> list:
    try:
        from check_body_style import check_day, load
    except Exception:
        return []
    rows = []
    for k in range(days, -1, -1):
        d = (date.today() - timedelta(days=k)).isoformat()
        sched = load(d)
        if not sched:
            continue
        _, stats = check_day(d, sched)
        if stats:
            rows.append((d, stats))
    return rows


def build(n: int) -> tuple:
    L = []
    today = date.today().isoformat()
    L.append(f"# リサーチ部門ダイジェスト（自動生成 {today}）\n")
    L.append("> **`research_digest.py` が生成。手で編集しない。**")
    L.append("> 週次企画（日曜）と日次執筆（毎朝）は、企画に入る前にこれを読む。\n")

    shelf = load_shelf()
    picked = pick_themes(shelf, n)
    L.append(f"## 1. 今週の題材候補（棚{len(shelf)}件からの輪番・{len(picked)}件）\n")
    L.append("**そのまま投稿にしない。**必ず読者の場面へ翻訳する")
    L.append("（読者＝月商100万円以上・自費中心・売上は伸びているが時間がない治療院経営者）。")
    L.append("翻訳できない題材は飛ばしてよい。\n")
    for cat, title, point in picked:
        L.append(f"- **{title}**（{cat}） — {point}" if point else f"- **{title}**（{cat}）")
    L.append("")

    voices = recent_reader_voices()
    L.append(f"## 2. 読者の声（直近30日・{len(voices)}件）\n")
    if voices:
        for v in voices[:30]:
            L.append(f"- [{v.get('post_date')} {v.get('slot')}] @{v.get('username')}: {v.get('text','')[:120]}")
    else:
        L.append("**0件。** 読者からの返信がまだ届いていない。")
        L.append("いいねも直近24日で13件しかない（[[エンゲージ率の偽装発覚]]参照）。")
        L.append("→ 題材を変えるより先に、**絡み（人間が他アカウントに反応しに行く仕事）**を疑う段階。")
    L.append("")

    used = used_themes()
    L.append(f"## 3. 直近14日で使ったテーマ（重複回避用・{sum(used.values())}枠）\n")
    if used:
        for t, c in used.most_common(15):
            mark = " ⚠️多い" if c >= 8 else ""
            L.append(f"- {t}: {c}回{mark}")
    else:
        L.append("- 直近のweekly_planが見つかりません")
    L.append("")

    bias = skeleton_bias()
    L.append("## 4. 本文の骨格の偏り（直近14日）\n")
    if bias:
        L.append("| 日付 | 枠 | 最頻の骨格 | 占有率 |")
        L.append("|:--|--:|:--|--:|")
        for d, s in bias:
            flag = " ⚠️" if s["skeleton_rate"] > 40 else ""
            L.append(f"| {d} | {s['slots']} | {s['skeleton_top']} | {s['skeleton_rate']}%{flag} |")
        L.append("")
        L.append("上限は40%（`check_body_style.py`）。超えた日は本文が1つの型に固まっている。")
    else:
        L.append("- 原稿が見つかりません")
    L.append("")
    return "\n".join(L), picked


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    args = sys.argv[1:]
    n = int(args[args.index("--n") + 1]) if "--n" in args else 20
    content, picked = build(n)
    if "--print" in args:
        print(content)
        return 0
    OUT.write_text(content, encoding="utf-8")
    remember(picked)
    print(f"リサーチダイジェストを生成: {OUT}（題材{len(picked)}件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
