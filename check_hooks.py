"""週次プランのフックが hook_rules.md「最優先原則0」の下限表を満たすか機械検査する。

2026-08-27新設。背景: ルール上は「1日に最低1本は数字型」と決まっていたのに、
2026-08の実績は金額入りフックが1日0.5本・views最下位の「〜な院は」構文が2.4本と、
ルールと真逆になっていた。文書に書くだけでは守られないので数えて落とす。

使い方:
    python check_hooks.py                      # 直近の weekly_plan を検査
    python check_hooks.py posts/weekly_plan/2026-08-31.json
終了コード 1 = 違反あり（週次企画はこれが 0 になるまでフックを直す）
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
PLAN_DIR = BASE / "posts" / "weekly_plan"

# 原則0の実測（2026-03〜08・3,512投稿）。括弧内はホームラン寄与倍率。
# 下限・上限は「1日の枠数に対する比率」で持つ（2026-08-27にSLOT_PLANを10→24枠へ拡張したため、
# 本数で固定すると枠を増減させるたびに基準が壊れる）。
FEATURES = {
    "金額": (r"[0-9０-９][0-9０-９,，]*\s*(円|万)", 0.30, "拡散"),                        # 2.09x
    "N選": (r"[0-9０-９一二三四五六七八九十]+\s*(つ|個|選|点|ステップ)", 0.20, "拡散・信頼"),  # 1.94x
    "期間": (r"[0-9０-９]+\s*(年|ヶ月|か月|カ月|週間|日|時間|分)", 0.20, "拡散・信頼"),        # 1.62x
    "呼びかけ": (r"(あなた|院長|先生)", 0.30, "全層"),                                    # 1.52x
}
# 上限（拡散枠で使うとホームランが消える要素）
LIMITS = {
    "「〜な院は」構文": (r"院(は|には|ほど|こそ)", 0.10),   # 0.45x・2026-08は24%を占めていた
    "一人称「僕」": (r"僕", 0.20),                        # HR 0.00x（信頼・会話のみ）
}
# 拡散枠では0本でなければならない要素
DIFFUSION_BAN = {
    "一人称「僕」": r"僕",
    "カギカッコのセリフ": r"[「『]",
    "疑問形の書き出し": r"(か|かも)[。．]?$",
    "感情語": r"(怖|不安|辛|しんど|泣|悔し|孤独|夜|涙|限界|逃げ|後悔|恥)",
}


def _floor(ratio: float, n: int) -> int:
    """枠数nに対する下限本数（最低1本は必ず要求する）"""
    return max(1, round(ratio * n))


def check_day(date: str, entries: list) -> list:
    """1日分のフックを検査して違反メッセージのリストを返す"""
    ng = []
    hooks = [(e.get("slot"), e.get("hook") or "", e.get("layer") or "") for e in entries]
    n = len(hooks)
    for name, (pat, ratio, layer) in FEATURES.items():
        floor = _floor(ratio, n)
        hit = [s for s, h, _ in hooks if re.search(pat, h)]
        if len(hit) < floor:
            ng.append(f"  ✗ {name}: {len(hit)}本（{n}枠なら下限{floor}本・置く層={layer}）")
    for name, (pat, ratio) in LIMITS.items():
        cap = _floor(ratio, n)
        hit = [s for s, h, _ in hooks if re.search(pat, h)]
        if len(hit) > cap:
            ng.append(f"  ✗ {name}: {len(hit)}本（{n}枠なら上限{cap}本）→ {', '.join(hit)}")
    for s, h, layer in hooks:
        if layer != "拡散":
            continue
        for name, pat in DIFFUSION_BAN.items():
            if re.search(pat, h):
                ng.append(f"  ✗ 拡散枠 {s} に「{name}」: {h[:30]}")
    return ng


def main():
    if len(sys.argv) > 1:
        files = [Path(sys.argv[1])]
    else:
        files = sorted(PLAN_DIR.glob("*.json"))[-1:]
    bad = 0
    for f in files:
        plan = json.loads(f.read_text(encoding="utf-8"))
        print(f"■ {f.name}")
        for date, entries in sorted((plan.get("days") or {}).items()):
            ng = check_day(date, entries)
            if ng:
                bad += 1
                print(f"{date} NG")
                print("\n".join(ng))
            else:
                print(f"{date} OK")
    if bad:
        print(f"\n{bad}日分が下限表を満たしていません（hook_rules.md 最優先原則0）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
