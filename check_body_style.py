"""本文（2投稿目以降）の「型の固着」と「AI臭の再発」を機械検査する。

2026-09-04新設。背景と根拠:
  ・taboo.md #7「同じ型・語尾の連続使用に注意（鮮度管理）」には、フック側の
    check_hooks.py に相当する機械検査が無く、本文は誰も数えていなかった。
  ・実測（2026-06以降・実測のある48日）で、1日の本文の「最頻の骨格」が占める
    割合の中央値は 50%。8/12〜8/22 はセリフ型が 70〜80%、8/26〜8/29 は番号列挙が
    60〜80% と、週単位で1つの型に固着していた。読者から見ると同じ投稿が並ぶ。
  ・骨格が散っていた日（集中度50%未満・6日）の ER 中央値は 6.26%、
    偏っていた日（42日）は 3.92%。ただし散った日のサンプルが6日しかないため、
    因果は未確定。この検査は「落とす」より「偏りを見えるようにする」ことが目的。
  ・語彙のAI臭（「〜ではないでしょうか」「ポイントは」「〜と言えるでしょう」等）は
    2,963件の実測で 0〜5件しか出ておらず、既存ルールで実質解決済み。
    ここでは再発検知（1件出たら知らせる）として持つ。

しきい値は「1日の枠数に対する比率」で持つ（SLOT_PLAN が 10→24 枠と変わっても壊れないように）。

使い方:
    python check_body_style.py                    # 今日と明日分を検査
    python check_body_style.py 2026-09-05
    python check_body_style.py --days 14          # 直近14日分をまとめて検査
    python check_body_style.py --json             # 機械可読で出力
終了コード 1 = 違反あり
"""
import io
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
POSTS_DIR = BASE / "posts"

# ── 骨格の分類（上から順に判定・1本文につき1つ） ──────────────────
SKELETONS = [
    ("番号列挙", r"①.*②"),
    ("中黒列挙", r"(?m)^[・･]"),
    ("セリフ", r"[「『][^」』]{4,}[」』]"),
    ("回想", r"(ました|でした)。"),
]
SKELETON_CAP = 0.40   # 最頻骨格が1日の何割まで許されるか（実測中央値は0.50）

# ── AI定型句の再発検知（実測2,963件で0〜5件しか出ていない＝出たら異常） ──
AI_PHRASES = {
    "〜ではないでしょうか": r"ではないでしょうか",
    "〜と言えます/言えるでしょう": r"と言え(ます|るでしょう)",
    "ポイントは": r"ポイントは",
    "重要なのは/大切なのは": r"(重要|大切)なのは",
    "いかがでしょうか": r"いかがでしょう",
    "〜という点です": r"という点(です|で、)",
    "しっかりと": r"しっかりと",
    "そのため": r"そのため",
    "なぜなら": r"なぜなら",
    "〜させていただきます": r"させていただき",
}

# ── 反復の上限 ────────────────────────────────────────────
END_NGRAM = 6          # 文末を何字で見るか
END_CAP = 0.08         # 同一文末が本文の全文数に占める上限
CLOSING_NGRAM = 10     # ツリー最終行の末尾を何字で見るか
CLOSING_DUP_CAP = 1    # 同じ締め方は1日1本まで（CTA枠は別勘定）
QUESTION_CAP = 0.20    # 疑問形で締めるツリーの上限（gate.md #7「10枠中1〜2本」＝10〜20%）

CTA_MARK = r"(LINE|ライン|プロフィール|リットリンク|コメント)"
QUESTION_END = r"(ですか|ますか|ありますか|ませんか|でしょうか)[。？?]?$"


def classify(body: str) -> str:
    for name, pat in SKELETONS:
        if re.search(pat, body, re.S):
            return name
    return "その他"


def sentences(text: str):
    for s in re.split(r"(?<=[。！？\n])", text):
        s = s.strip()
        if len(s) >= 4:
            yield s


def check_day(date_str: str, schedule: dict) -> tuple:
    trees = {s: p for s, p in schedule.items() if isinstance(p, list) and len(p) >= 2}
    n = len(trees)
    if n == 0:
        return [], {}

    ng, warn = [], []
    bodies = {s: "\n".join(p[1:]) for s, p in trees.items()}

    # 1. 骨格の集中度
    skel = {s: classify(b) for s, b in bodies.items()}
    counts = Counter(skel.values())
    top, tv = counts.most_common(1)[0]
    cap = max(2, round(SKELETON_CAP * n))
    if tv > cap:
        slots = [s for s, k in sorted(skel.items()) if k == top]
        ng.append(f"  ✗ 骨格の固着: 「{top}」が{tv}/{n}本（{n}枠なら上限{cap}本）→ {', '.join(slots)}")

    # 2. AI定型句の再発
    for name, pat in AI_PHRASES.items():
        hit = sorted(s for s, b in bodies.items() if re.search(pat, b))
        if hit:
            warn.append(f"  ! AI定型句「{name}」: {', '.join(hit)}")

    # 3. 文末の反復
    ends = Counter()
    total = 0
    for b in bodies.values():
        for s in sentences(b):
            ends[s.rstrip("。！？")[-END_NGRAM:]] += 1
            total += 1
    if total:
        for end, c in ends.most_common(5):
            if c / total > END_CAP and c >= 3:
                warn.append(f"  ! 文末の反復「…{end}」が{c}回（全{total}文の{c/total*100:.0f}%）")

    # 4. 締め方の重複（CTA枠は定型なので別勘定）
    closings = Counter()
    for s, p in trees.items():
        last = p[-1].strip()
        if re.search(CTA_MARK, last):
            continue
        closings[last.rstrip("。！？")[-CLOSING_NGRAM:]] += 1
    for c_text, c in closings.most_common(3):
        if c > CLOSING_DUP_CAP:
            ng.append(f"  ✗ 締めの重複「…{c_text}」が{c}本（上限{CLOSING_DUP_CAP}本）")

    # 5. 疑問形で締めるツリーの本数
    q = sorted(s for s, p in trees.items()
               if re.search(QUESTION_END, p[-1].strip().rstrip("　 ")))
    qcap = max(1, round(QUESTION_CAP * n))
    if len(q) > qcap:
        ng.append(f"  ✗ 疑問形の締めが{len(q)}本（{n}枠なら上限{qcap}本・gate.md #7）→ {', '.join(q)}")

    stats = {
        "slots": n,
        "skeleton_top": top,
        "skeleton_top_n": tv,
        "skeleton_rate": round(tv / n * 100, 1),
        "skeletons": dict(counts),
        "question_closings": len(q),
        "ng": len(ng),
        "warn": len(warn),
    }
    return ng + warn, stats


def load(date_str: str):
    f = POSTS_DIR / f"{date_str}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    # Windowsのcp932コンソールでも記号が出せるようにする
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]

    if "--days" in args:
        i = args.index("--days")
        days = int(args[i + 1])
        today = date.today()
        targets = [(today - timedelta(days=k)).isoformat() for k in range(days, -1, -1)]
    elif args:
        targets = args
    else:
        today = date.today()
        targets = [today.isoformat(), (today + timedelta(days=1)).isoformat()]

    bad = 0
    out = {}
    for d in targets:
        schedule = load(d)
        if not schedule:
            continue
        msgs, stats = check_day(d, schedule)
        if not stats:
            continue
        out[d] = {"messages": msgs, **stats}
        if stats["ng"]:
            bad += 1
        if not as_json:
            head = f"{d}  {stats['slots']}枠  最頻骨格 {stats['skeleton_top']} {stats['skeleton_rate']}%"
            print(f"{head}  {'NG' if stats['ng'] else 'OK'}")
            for m in msgs:
                print(m)

    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif bad:
        print(f"\n{bad}日分に違反があります（本文の型の固着・taboo.md #7）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
