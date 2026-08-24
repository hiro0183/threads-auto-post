"""
到達率モニタ（2026-08-24新設）

「原稿が生成されたか」ではなく「**実際にThreadsに出たか**」を唯一の正として測る。

背景（事故の記録）:
  2026-08-03〜08-24の22日間、POST_SCHEDULEとSLOT_PLANのズレにより10枠中7枠が
  毎日空振りしていた。しかし当時の監視はすべて「社内の書類」——原稿ファイルの
  存在・週次プランの有無・検品の合否——しか見ておらず、22日間ずっと緑を出し続けた。
  Threads APIを1回叩けば3秒で分かる異常だった。

  → 判定は必ず実物（Threads API）で行う。ファイルの存在で緑を出さない。

使い方:
  python reach_check.py            # 直近7日の到達率
  python reach_check.py 14         # 直近14日
"""

import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
JST = timezone(timedelta(hours=9))

# 実測を保存する先（司令室・週次レポート・実験台帳が共通で読む）
REACH_STATUS_FILE = BASE_DIR / "reach_status.json"

# スロット対応づけの許容幅。Render再起動後のrecover_missed_slotsで
# 数時間遅れて投稿されることがあるため広めに取る。
SLOT_MATCH_MINUTES = 180


def fetch_recent_posts(token: str, limit: int = 100) -> list:
    """自分の投稿（ツリーのルートのみ）を新しい順に取得する。

    /me/threads はツリーの返信を含まずルート投稿だけを返すため、
    「1スロット＝1件」として数えられる。
    """
    posts = []
    url = "https://graph.threads.net/v1.0/me/threads"
    params = {"fields": "id,timestamp,text", "limit": min(limit, 100), "access_token": token}
    while url and len(posts) < limit:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Threads API {r.status_code}: {r.text[:200]}")
        body = r.json()
        for row in body.get("data", []):
            ts = datetime.strptime(row["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(JST)
            posts.append({"id": row["id"], "jst": ts, "text": row.get("text") or ""})
        nxt = body.get("paging", {}).get("next")
        url, params = (nxt, None) if nxt else (None, None)
    return posts[:limit]


def _assign_slots(posts: list, slots: list) -> tuple[dict, list]:
    """投稿をスロットへ1対1（貪欲法・投稿の古い順）で割り当てる。

    2026-08-24の事故の教訓は「ファイルの存在で緑を出さない」ことだったが、
    旧実装は複数の投稿が同じ最近傍スロットにマッチしても matched は1件しか
    増えない一方 actual は生の投稿件数のままだったため、
    『重複投稿1件＋本当の欠落1件』が起きると件数だけ帳尻が合って
    到達率100%に見えてしまう＝同じ種類の誤検知を再現しかねない構造だった。
    ここでスロットを使い切り制にし、1スロット=1投稿の対応を保証する。
    戻り値: (slot -> post の割当dict, どのスロットにもマッチしなかった投稿のリスト)"""
    remaining = list(slots)
    assigned: dict = {}
    extra: list = []
    for p in sorted(posts, key=lambda x: x["jst"]):
        minutes = p["jst"].hour * 60 + p["jst"].minute
        best, best_diff = None, None
        for s in remaining:
            h, m = map(int, s.split(":"))
            diff = abs(minutes - (h * 60 + m))
            if diff <= SLOT_MATCH_MINUTES and (best_diff is None or diff < best_diff):
                best, best_diff = s, diff
        if best:
            assigned[best] = p
            remaining.remove(best)
        else:
            extra.append(p)
    return assigned, extra


def daily_reach(days: int = 7, token: str | None = None) -> list:
    """直近days日の日別到達率を返す（新しい順）。

    戻り値: [{"date","expected","actual","rate","missing","matched"}, ...]
    当日は途中経過になるため含めない（前日までを対象）。
    """
    from post_runner import SLOT_PLAN
    if token is None:
        from token_manager import get_access_token
        token = get_access_token()

    slots = list(SLOT_PLAN.keys())
    expected = len(slots)

    today = datetime.now(JST).date()
    target_dates = [(today - timedelta(days=i)).isoformat() for i in range(1, days + 1)]

    # 1日10枠×日数 + 余裕
    posts = fetch_recent_posts(token, limit=min(100, max(30, expected * days + 20)))

    by_date: dict[str, list] = {d: [] for d in target_dates}
    for p in posts:
        d = p["jst"].date().isoformat()
        if d in by_date:
            by_date[d].append(p)

    result = []
    for d in target_dates:
        rows = by_date[d]
        assigned, extra = _assign_slots(rows, slots)
        actual = len(assigned)
        result.append({
            "date": d,
            "expected": expected,
            "actual": actual,
            "rate": round(actual / expected * 100, 1) if expected else 0.0,
            "matched": sorted(assigned.keys()),
            "missing": [s for s in slots if s not in assigned],
            # スロットにマッチしなかった投稿（手動投稿・重複投稿・想定外時刻など）。
            # actual/rateには含めない＝スロット被覆率を歪ませない。
            "unmatched_posts": len(extra),
        })
    return result


def build_status(days: int = 7, token: str | None = None) -> dict:
    """到達率のサマリーを組み立てる（司令室・週次レポート共通の入力）"""
    rows = daily_reach(days=days, token=token)
    yesterday = rows[0] if rows else None
    # 連続で100%を割っている日数（直近から数える）
    streak = 0
    for r in rows:
        if r["rate"] >= 100:
            break
        streak += 1
    total_exp = sum(r["expected"] for r in rows)
    total_act = sum(r["actual"] for r in rows)
    return {
        "updated": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "days": days,
        "yesterday": yesterday,
        "week_rate": round(total_act / total_exp * 100, 1) if total_exp else 0.0,
        "miss_streak": streak,
        "alert": bool(yesterday and yesterday["rate"] < 100),
        "daily": rows,
    }


def save_status(status: dict) -> Path:
    REACH_STATUS_FILE.write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return REACH_STATUS_FILE


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 7
    status = build_status(days=days)
    save_status(status)

    print(f"到達率モニタ（{status['updated']} 時点・直近{days}日）")
    print(f"  週の到達率: {status['week_rate']}%")
    print()
    print("  日付        出た/予定   到達率   出なかった枠")
    for r in status["daily"]:
        mark = "OK " if r["rate"] >= 100 else "NG "
        miss = ",".join(r["missing"]) if r["missing"] else "-"
        print(f"  {mark}{r['date']}  {r['actual']:>2}/{r['expected']:<2}    {r['rate']:>5}%   {miss}")

    if status["alert"]:
        print()
        print(f"  [ALERT] 前日の到達率が100%未満です（{status['miss_streak']}日連続）")
    print()
    print(f"  保存: {REACH_STATUS_FILE}")


if __name__ == "__main__":
    main()
