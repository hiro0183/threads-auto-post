"""
実験台帳（2026-08-24新設）— PDCAの「回す」側の本体

背景:
  週次企画は毎週 directives（改善指示）を書いていたが、自然言語の書き捨てで、
  「翌週それが守られたか」「効いたか」を誰も検証していなかった。結果、
  2026-08-04に決めた「AI切り口を4週間観察する」という約束は、一度も
  観測されないまま3週間が過ぎた。仮説が開きっぱなしになる構造だった。

  → 仮説をカードにし、開いたら必ず閉じる。

役割分担:
  開く   : 週次企画（クラウド・日曜）が新しいカードを追加する
  埋める : weekly_report.py / このスクリプトが実測から result を自動で埋める
  閉じる : 人間が月曜に verdict（続行/中止/変更）を書き込む

ルール:
  - 同時に開けるカードは最大3枚（散らかると何も検証できない）
  - judge_on を過ぎたカードは必ず閉じる
  - 判定に足るサンプル（min_sample）が無いうちは「判定不可」とする

使い方:
  python ledger.py              # 台帳の状況を表示
  python ledger.py --update     # 実測から result を埋めて保存
"""

import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
LEDGER_FILE = BASE_DIR / "experiments" / "ledger.json"
JST = timezone(timedelta(hours=9))

MAX_OPEN = 3

METRICS = {
    "engagement_rate": "エンゲージ率(%)",
    "views_median": "views中央値",
    "reach_rate": "到達率(%)",
    "followers_delta": "フォロワー純増(週)",
}


def load() -> dict:
    if not LEDGER_FILE.exists():
        return {"cards": []}
    return json.loads(LEDGER_FILE.read_text(encoding="utf-8"))


def save(data: dict):
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def open_cards(data: dict) -> list:
    return [c for c in data.get("cards", []) if not c.get("verdict")]


# ── 実測の取り出し ──────────────────────────────────────

def _load_insights() -> list:
    f = BASE_DIR / "insights_data.jsonl"
    if not f.exists():
        f = BASE_DIR / "sync" / "insights_data.jsonl"
    if not f.exists():
        return []
    rows, seen = [], set()
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        rid = r.get("root_id")
        if rid and rid in seen:
            continue
        if rid:
            seen.add(rid)
        if isinstance(r.get("views"), int) and r["views"] > 0:
            rows.append(r)
    return rows


def _engagement_rate(r: dict):
    v = r.get("views") or 0
    if not v:
        return None
    eng = sum(r.get(k) or 0 for k in ("likes", "replies", "reposts", "quotes"))
    return eng / v * 100


def _median(xs: list):
    if not xs:
        return None
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _matches(row: dict, filt: dict) -> bool:
    if not filt:
        return True
    slots = filt.get("slots")
    if slots and row.get("slot") not in slots:
        return False
    keywords = filt.get("keywords")
    if keywords:
        blob = (row.get("catch") or "") + " ".join(row.get("posts") or [])
        if not any(k in blob for k in keywords):
            return False
    return True


def measure(card: dict) -> dict:
    """カードの指標を実測から計算して {"value","sample"} を返す"""
    metric = card.get("metric")
    since = card.get("opened")

    if metric == "reach_rate":
        f = BASE_DIR / "reach_status.json"
        if not f.exists():
            return {"value": None, "sample": 0}
        st = json.loads(f.read_text(encoding="utf-8"))
        daily = [d for d in st.get("daily", []) if d["date"] >= since]
        if not daily:
            return {"value": None, "sample": 0}
        exp = sum(d["expected"] for d in daily)
        act = sum(d["actual"] for d in daily)
        return {"value": round(act / exp * 100, 1) if exp else None, "sample": len(daily)}

    if metric == "followers_delta":
        f = BASE_DIR / "follower_log.jsonl"
        if not f.exists():
            f = BASE_DIR / "sync" / "follower_log.jsonl"
        if not f.exists():
            return {"value": None, "sample": 0}
        pts = []
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            date = str(d.get("date") or d.get("timestamp") or "")[:10]
            cnt = d.get("followers_count") or d.get("count") or d.get("followers")
            if date >= since and isinstance(cnt, int):
                pts.append((date, cnt))
        pts.sort()
        if len(pts) < 2:
            return {"value": None, "sample": len(pts)}
        days = max(1, (datetime.fromisoformat(pts[-1][0]) - datetime.fromisoformat(pts[0][0])).days)
        return {"value": round((pts[-1][1] - pts[0][1]) / days * 7, 1), "sample": len(pts)}

    rows = [r for r in _load_insights()
            if str(r.get("date", "")) >= since and _matches(r, card.get("filter") or {})]
    if not rows:
        return {"value": None, "sample": 0}

    if metric == "views_median":
        return {"value": _median([r["views"] for r in rows]), "sample": len(rows)}

    ers = [x for x in (_engagement_rate(r) for r in rows) if x is not None]
    return {"value": round(_median(ers), 2) if ers else None, "sample": len(ers)}


def update(data: dict) -> dict:
    today = datetime.now(JST).date().isoformat()
    for card in data.get("cards", []):
        if card.get("verdict"):
            continue
        card["result"] = measure(card)
        card["result"]["measured_at"] = today
        base = card.get("baseline")
        val = card["result"]["value"]
        if val is not None and isinstance(base, (int, float)) and base:
            card["result"]["vs_baseline"] = str(round(val / base * 100)) + "%"
        card["due"] = card.get("judge_on", "") <= today
        card["enough_sample"] = card["result"]["sample"] >= (card.get("min_sample") or 0)
    return data


# ── 表示 ───────────────────────────────────────────────

def render_markdown(data: dict) -> str:
    today = datetime.now(JST).date().isoformat()
    L = []
    L.append("## 実験台帳（開いている仮説）")
    L.append("")
    cards = open_cards(data)
    if not cards:
        L.append("開いている仮説はありません。")
    else:
        L.append("| ID | 仮説 | 指標 | ベースライン | 実測 | 対比 | n | 判定日 | 状態 |")
        L.append("|:--|:--|:--|--:|--:|--:|--:|:--|:--|")
        for c in cards:
            res = c.get("result") or {}
            val = res.get("value")
            due = c.get("judge_on", "") <= today
            enough = res.get("sample", 0) >= (c.get("min_sample") or 0)
            state = "判定待ち" if (due and enough) else ("サンプル不足" if due else "観察中")
            L.append("| {id} | {h} | {m} | {b} | {v} | {r} | {n} | {j} | {s} |".format(
                id=c.get("id", ""), h=c.get("hypothesis", "")[:34],
                m=METRICS.get(c.get("metric"), c.get("metric", "")),
                b=c.get("baseline", "-"), v="-" if val is None else val,
                r=res.get("vs_baseline", "-"), n=res.get("sample", 0),
                j=c.get("judge_on", "-"), s=state))
    closed = [c for c in data.get("cards", []) if c.get("verdict")]
    if closed:
        L.append("")
        L.append("### 閉じた仮説（直近5件）")
        L.append("")
        for c in closed[-5:]:
            note = "（" + c["note"] + "）" if c.get("note") else ""
            L.append("- **" + str(c.get("id")) + "** " + str(c.get("hypothesis"))
                     + " → **" + str(c.get("verdict")) + "**" + note)
    L.append("")
    L.append("> 同時に開けるのは最大" + str(MAX_OPEN) + "枚。judge_onを過ぎたカードは"
             "「続行 / 中止 / 変更」のいずれかを verdict に書いて閉じること。")
    return chr(10).join(L)


def main():
    data = load()
    if "--update" in sys.argv:
        data = update(data)
        save(data)
        print("実測を反映しました")
    else:
        data = update(data)
    print()
    print(render_markdown(data))
    n = len(open_cards(data))
    if n > MAX_OPEN:
        print()
        print("[WARN] 開いているカードが" + str(n) + "枚あります（上限"
              + str(MAX_OPEN) + "枚）。どれかを閉じてください")


if __name__ == "__main__":
    main()
