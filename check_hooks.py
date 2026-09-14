"""週次プランのフックが hook_rules.md「最優先原則0」の下限表を満たすか機械検査する。

2026-08-27新設。背景: ルール上は「1日に最低1本は数字型」と決まっていたのに、
2026-08の実績は金額入りフックが1日0.5本・views最下位の「〜な院は」構文が2.4本と、
ルールと真逆になっていた。文書に書くだけでは守られないので数えて落とす。

使い方:
    python check_hooks.py                      # 直近の weekly_plan を検査
    python check_hooks.py posts/weekly_plan/2026-08-31.json
終了コード 1 = 違反あり（週次企画はこれが 0 になるまでフックを直す）
"""
import difflib
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
PLAN_DIR = BASE / "posts" / "weekly_plan"
POSTS_DIR = BASE / "posts"

# 原則0の実測（2026-03〜08・3,512投稿）。括弧内はホームラン寄与倍率。
# 下限・上限は「1日の枠数に対する比率」で持つ（2026-08-27にSLOT_PLANを10→24枠へ拡張したため、
# 本数で固定すると枠を増減させるたびに基準が壊れる）。
FEATURES = {
    # 2026-09-13になりあいさん決定で 30%(24枠=7本) → 17%(24枠=4本)。理由は hook_rules.md 掟3。
    # 承認済みの金額が6種しかなく、7本×7日=週49本を6種で埋めると必ず創作が混ざっていた。
    "金額": (r"[0-9０-９][0-9０-９,，]*\s*(円|万)", 0.17, "拡散"),                        # 2.09x
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


# フックの字数（hook_rules.md / weekly_plan_routine.md「10〜25字・最大35字」）
HOOK_MIN_LEN = 10
HOOK_MAX_LEN = 35

# 2026-09-13追加: 自院の商品価格として使ってよい金額は persona.md の3つだけ。
# 背景: 2026-09-14週の168フックに「初回価格6,000円」「10,000円台のコース」「7,000円台の
# 本命コース」「客単価12,000円」が混在していた。どれも本人確認を経ていない架空の価格で、
# しかも枠ごとに額が食い違っていた（同じ「16:00」が日によって6,000円・7,000円・10,000円）。
# 原因は金額フックの下限が30%（24枠なら7本）あるのに、承認済みの金額が数えるほどしかなく、
# 足りない分を生成側が創作していたこと。基準値（広告費・固定費・家賃などの一般的な水準）は
# hook_rules.md が推奨しているので落とさず、「自院の商品価格」を名指しする言い回しだけを見る。
OWN_PRICE_CONTEXT = r"(コース|本命|初回価格|価格は|単価|料金|回数券|メニュー)"
APPROVED_PRICES = ("300円", "15,000円", "35,000円", "5,000円")


def check_own_price(hooks) -> list:
    """自院の商品価格として、persona.md にない金額を名乗っていないか"""
    ng = []
    money = re.compile(r"[0-9０-９][0-9０-９,，]*\s*円(台)?")
    ctx = re.compile(OWN_PRICE_CONTEXT)
    for s, h, _ in hooks:
        for m in money.finditer(h):
            amount = m.group(0).replace("台", "")
            if amount in APPROVED_PRICES:
                continue
            # 金額の前後12字に「コース」「単価」等があれば自院の商品価格とみなす
            around = h[max(0, m.start() - 12): m.end() + 12]
            if ctx.search(around):
                ng.append(f"  ✗ 未承認の自院価格 {s}: 「{m.group(0)}」（persona.mdの承認額は"
                          f"{'/'.join(APPROVED_PRICES)}のみ）→ {h}")
    return ng


def check_slot_lock(days: dict) -> list:
    """同じスロットが週をまたいで同じ言い回しに固着していないか（2026-09-13追加）。

    2026-09-12の週次プラン検品で「19:30が6/7日『あなたの…』開始」が見つかり、直したはずが
    2026-09-14週では18:45が7/7日「〜派、〜派、あなたはどちら」で完全に固着していた。
    人が毎回読まないと気づけないので機械で数える。CTA枠(22:00)は締めをそろえてよいので除く。
    """
    ng = []
    byslot = {}
    for d, entries in days.items():
        for e in entries:
            byslot.setdefault(e.get("slot"), []).append(e.get("hook") or "")
    for slot, hooks in sorted(byslot.items()):
        if slot == "22:00" or len(hooks) < 3:
            continue
        c = Counter(h[-6:] for h in hooks if len(h) >= 6)
        if not c:
            continue
        tail, n = c.most_common(1)[0]
        if n >= 3:
            ng.append(f"  ✗ 同一スロットの固着 {slot}: 末尾「{tail}」が{n}/{len(hooks)}日")
    return ng


# ── 2026-09-14追加: 同日重複・14日重複の機械検査 ──────────────────────
#
# 背景: 2026-09-14の独立検品(12:00)で3日分18件のNGが出たが、そのほぼ全部が
# 「週次プランが同じ承認済み金額(35,000円/15,000円/5,000円)と同じフックの
# 雛形（『35,000円+値段の前に何かを渡す/伝える/減らす』型等）を14日以内、
# 時には同日内で使い回していた」ことが原因だった。check_hooks.py はそれまで
# 1日ぶんの型比率としきい値・同一スロットの週またぎ固着しか見ておらず、
# 「同じ日の中の重複」「14日以内の言い回し・金額の再訪」を一度も数えていな
# かった。taboo.md #2（14日重複禁止・同じ日の中でも重複させない）は文書に
# あったが機械検査が無かったので、週次企画のたびに人間が気づくまで素通りし
# ていた。以下はそれを埋める。

AMOUNT_RE = re.compile(r"[0-9０-９][0-9０-９,，]*\s*(円|万)")
KANJI_KATAKANA = re.compile(r"[一-鿿゠-ヿ]")
CTA_PHRASE = "経営の問診"

# 2026-09-14追加: 「自院の価格」として名乗っている金額だけを見る（check_own_priceの
# OWN_PRICE_CONTEXTと同じ発想）。広告費・固定費・家賃・人件費などの一般的な水準は
# hook_rules.mdが推奨する比較材料で、毎回別の額を使ってよいので対象に含めない。
_PRICE_CTX = re.compile(OWN_PRICE_CONTEXT)


def _kanji_windows(h: str, length: int) -> set:
    """h から長さlengthの部分文字列で、漢字かカタカナを1字以上含むものだけを集める"""
    return {
        h[i:i + length]
        for i in range(len(h) - length + 1)
        if KANJI_KATAKANA.search(h[i:i + length])
    }


def _amounts(h: str) -> set:
    return {m.group(0) for m in AMOUNT_RE.finditer(h)}


def _own_price_amounts(h: str) -> set:
    """hの中で「自院の価格」として使われている金額だけを返す（check_own_priceと同じ判定）"""
    out = set()
    for m in AMOUNT_RE.finditer(h):
        around = h[max(0, m.start() - 12): m.end() + 12]
        if _PRICE_CTX.search(around):
            out.add(m.group(0))
    return out


def _normalize_amounts(h: str) -> str:
    """金額の数字部分を1文字のプレースホルダに置き換える（2026-09-14追加）。

    承認済みの自院価格は35,000円/15,000円/300円/5,000円の実質4種しかなく（persona.md）、
    「◯◯円の」のような数字+助詞の並びは、それだけでほぼ毎日どこかのフックに出てくる。
    ここを生の文字列のまま部分文字列/類似度の比較に使うと、本当に言い回し（型）が
    似ているわけではなく単に同じ承認済み金額を使っただけの組み合わせまで大量にNGになる
    （2026-09-14実測: 素の実装で1日あたり10〜30件の誤検知）。金額を1字に畳んでから
    比較することで、「型」としての一致だけを見るようにする。
    """
    return AMOUNT_RE.sub("＃", h)


def check_same_day(entries: list) -> list:
    """1日の中でのフック重複を検査する（2026-09-14新設。背景は上のコメント参照）。

    - 冒頭7字が同じフックが2本以上
    - 漢字/カタカナを含む8字以上の部分文字列が2本以上のフックに共通（金額は畳んで比較）
    - 漢字/カタカナを含む6字以上の部分文字列が3本以上のフックに共通（同上）
    - 「自院の価格」として使っている金額の文字列（例「35,000円」）が2本以上のフックに共通
      （広告費・固定費など一般的な水準の金額は対象外。理由は_PRICE_CTXのコメント参照）
    22:00のCTA枠は、共通部分が「経営の問診」というCTA定型句そのものの場合のみ、
    部分文字列系の判定から除外する（毎日同じCTA文言を使うのは仕様であって重複事故ではないため）。
    """
    ng = []
    hooks = [(e.get("slot"), e.get("hook") or "") for e in entries]

    # 冒頭7字の一致
    heads = {}
    for s, h in hooks:
        if len(h) < 7:
            continue
        heads.setdefault(h[:7], []).append(s)
    for head, slots in heads.items():
        if len(slots) >= 2:
            ng.append(f"  ✗ 同日重複(冒頭7字)「{head}…」: {', '.join(slots)}")

    # 漢字/カタカナを含む部分文字列の一致（8字→2本、6字→3本。金額は畳んで比較）
    for length, min_hit in ((8, 2), (6, 3)):
        windows = {}
        for s, h in hooks:
            for w in _kanji_windows(_normalize_amounts(h), length):
                if s == "22:00" and w == CTA_PHRASE:
                    continue
                windows.setdefault(w, set()).add(s)
        seen = set()
        for w, slots in windows.items():
            if len(slots) >= min_hit and w not in seen:
                seen.add(w)
                ng.append(f"  ✗ 同日重複({length}字以上)「{w}」: {', '.join(sorted(slots))}")

    # 自院の価格として使っている金額が2本以上（一般的な水準の金額は対象外）
    amounts = {}
    for s, h in hooks:
        for a in _own_price_amounts(h):
            amounts.setdefault(a, set()).add(s)
    for a, slots in amounts.items():
        if len(slots) >= 2:
            ng.append(f"  ✗ 同日重複(自院価格「{a}」): {', '.join(sorted(slots))}")
    return ng


def _load_posts_hooks(date_str: str) -> dict:
    """posts/{date}.json からスロット別フック（posts[slot][0]の1行目）を読む。無ければ{}"""
    f = POSTS_DIR / f"{date_str}.json"
    if not f.exists():
        return {}
    try:
        posts = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for slot, tree in posts.items():
        if isinstance(tree, list) and tree:
            first = str(tree[0]).split("\n")[0].strip()
            if first:
                out[slot] = first
    return out


def _build_history(all_days: dict, target_date: str) -> dict:
    """target_date より前14日分の「投稿済み or 計画済み」フックを {日付: {slot: hook}} で返す。

    posts/{d}.json（実際に書いた原稿）があればそれを優先的な実測として使い、
    週次プラン自身のより早い日（posts/{d}.jsonがまだ無い9/18以降等）はプランの
    hookで補う。両方ある日はプラン側（＝直近で確定した値）を優先する。
    """
    d0 = date.fromisoformat(target_date)
    history = {}
    for k in range(1, 15):
        dd = (d0 - timedelta(days=k)).isoformat()
        hooks = _load_posts_hooks(dd)
        if hooks:
            history[dd] = hooks
    for dd, entries in all_days.items():
        if dd >= target_date:
            continue
        dd_date = date.fromisoformat(dd)
        if (d0 - dd_date).days > 14 or (d0 - dd_date).days < 1:
            continue
        day_hist = history.setdefault(dd, {})
        for e in entries:
            if e.get("slot") and e.get("hook"):
                day_hist[e["slot"]] = e["hook"]
    return history


# しきい値（2026-09-14実測でチューニング。根拠は check_history のdocstring）:
# - 22:00(CTA)は毎日似た言い回しで正常なので、22:00どうしの比較だけ高いしきい値にする
# - それ以外は素の0.60/8字だと「35,000円の」のような金額直後の助詞の並びだけで
#   ほぼ毎日ヒットしてしまう（実測: 9/14-17の4日で ratio0.60/8字なら平均約15件/日）。
#   金額を畳んで(=_normalize_amounts)から比較し、しきい値も0.72・11字に上げることで、
#   「同じ承認済み金額をまた使った」ではなく「言い回し（型）そのものが似ている」場合
#   だけを拾うようにした。これでも2026-09-14に人間が実際に手直しした重複型
#   （taboo.md#2の事例）は検出できることを確認済み。
HISTORY_RATIO = 0.72
HISTORY_RATIO_CTA = 0.80
HISTORY_SUBLEN = 11


def check_history(days: dict) -> dict:
    """14日以内に同系統のフック・金額が再訪していないか検査する（2026-09-14新設）。

    背景: 2026-09-14の独立検品で「35,000円+値段の前に何かを渡す/伝える/減らす」型が
    9/1・9/7・9/14週と14日以内に3周していた等、check_slot_lock（週またぎの同一スロット
    固着のみ）ではまったく捕まらない再発が繰り返し見つかった。ここでは実際に投稿された
    posts/{date}.json（無ければ週次プラン自身のより早い日）を「フックの履歴」として持ち、
    今回のプランの各フックをその履歴と照合する。

    「同じ金額の3周目」判定について: 承認済みの自院価格が実質2〜3種類しかなく
    （persona.md）、金額型フックの下限（hook_rules.md原則0）を満たすには14日の間に
    同じ金額を何度も使わざるを得ない。そのため「金額が2回出てきたら即NG」にすると
    毎日ほぼ確実にNGになり実用にならない（2026-09-14実測）。ここでは
    「同じ金額」かつ「型としきい値が同基準で一致する組が2件以上＝3周目」の場合だけを
    NGにし、単なる金額の再利用ではなく金額+言い回しのセットが繰り返し再訪している
    ケースに絞った。
    """
    result = {}
    for target_date in sorted(days.keys()):
        entries = days[target_date]
        history = _build_history(days, target_date)
        # 履歴を平坦なリストに（日付, スロット, hook）
        flat = [(dd, s, h) for dd, hs in history.items() for s, h in hs.items()]
        ng = []
        for e in entries:
            slot, hook = e.get("slot"), e.get("hook") or ""
            if not hook:
                continue
            is_cta = slot == "22:00"
            ratio_th = HISTORY_RATIO_CTA if is_cta else HISTORY_RATIO
            nhook = _normalize_amounts(hook)
            cur_windows = _kanji_windows(nhook, HISTORY_SUBLEN)
            cur_amounts = _own_price_amounts(hook)
            ratio_hits = []
            for dd, s2, h2 in flat:
                if is_cta and s2 != "22:00":
                    continue
                nh2 = _normalize_amounts(h2)
                ratio = difflib.SequenceMatcher(None, nhook, nh2).ratio()
                if ratio >= ratio_th:
                    ng.append(f"  ✗ 14日重複(類似度{ratio:.2f}) {slot}: 「{hook}」"
                               f" ← {dd} {s2}「{h2}」")
                    ratio_hits.append((dd, s2, h2, ratio))
                    continue
                shared = cur_windows & _kanji_windows(nh2, HISTORY_SUBLEN)
                shared = {w for w in shared
                          if not ((is_cta or s2 == "22:00") and w == CTA_PHRASE)}
                if shared:
                    ng.append(f"  ✗ 14日重複(部分文字列「{sorted(shared)[0]}」) {slot}: "
                               f"「{hook}」 ← {dd} {s2}「{h2}」")
            for a in cur_amounts:
                hit_dates = [
                    (dd, s2, h2) for dd, s2, h2 in flat
                    if a in _own_price_amounts(h2)
                    and difflib.SequenceMatcher(None, nhook, _normalize_amounts(h2)).ratio() >= ratio_th
                ]
                if len(hit_dates) >= 2:
                    dd, s2, h2 = hit_dates[0]
                    ng.append(f"  ✗ 同じ金額の3周目「{a}」 {slot}: 「{hook}」"
                               f" ← {dd} {s2}「{h2}」ほか{len(hit_dates)}件")
        if ng:
            result[target_date] = ng
    return result


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
    # 2026-09-12追加: フックの字数。hook_rules/weekly_plan_routine は「10〜25字・最大35字」と
    # 定めているのに、この検査は型の本数だけを見ていて字数を一度も数えていなかった。
    # 実際に 2026-09-13 の原稿で 46字（18:15）と 36字（16:30）が検査を通り抜けていた。
    for s, h, _ in hooks:
        if len(h) > HOOK_MAX_LEN:
            ng.append(f"  ✗ 字数超過 {s}: {len(h)}字（上限{HOOK_MAX_LEN}字）→ {h[:40]}")
        elif len(h) < HOOK_MIN_LEN:
            ng.append(f"  ✗ 字数不足 {s}: {len(h)}字（下限{HOOK_MIN_LEN}字）→ {h}")
    ng += check_own_price(hooks)
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
        days = plan.get("days") or {}
        history_ng = check_history(days)
        for date, entries in sorted(days.items()):
            ng = check_day(date, entries)
            ng += check_same_day(entries)
            ng += history_ng.get(date, [])
            if ng:
                bad += 1
                print(f"{date} NG")
                print("\n".join(ng))
            else:
                print(f"{date} OK")
        lock = check_slot_lock(plan.get("days") or {})
        if lock:
            bad += 1
            print("週全体 NG")
            print(chr(10).join(lock))
    if bad:
        print(f"\n{bad}日分が下限表を満たしていません（hook_rules.md 最優先原則0）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
