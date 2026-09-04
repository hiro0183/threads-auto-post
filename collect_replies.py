"""読者からの返信を集めて、投稿リサーチの材料にする（2026-09-04新設）。

背景:
  ・threads_api.py に get_replies() は前からあったが、一度も呼ばれていなかった。
    読者が実際に書いた言葉が毎日届いているのに、誰も読んでいない状態だった。
  ・あわせて、この収集で「返信数」の中身が分かる。Threads APIが返す replies は
    ツリーの2〜3投稿目（＝自分の返信）を含む。2026-09-04の実測では、
    views>=10 の3,440件のうち 99% で replies == 自分のツリー投稿数 だった。
    つまり従来のエンゲージ率は自作自演分を数えている。ここで own/reader を分けて記録し、
    reader_engagement（読者だけの反応）を正として残す。

使い方:
    python collect_replies.py                # 直近3日分の投稿の返信を収集
    python collect_replies.py --days 14      # 直近14日分
    python collect_replies.py --digest       # 溜まった読者の声を一覧で出す
    python collect_replies.py --digest --days 30

出力:
    replies_collected.jsonl  … 読者の返信（1行1件・id で重複排除）
    reply_stats.jsonl        … 投稿ごとの own/reader 内訳（ER補正の材料）
"""
import io
import json
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import requests

from threads_auth import load_tokens

BASE = Path(__file__).resolve().parent
INSIGHTS = BASE / "insights_data.jsonl"
OUT_REPLIES = BASE / "replies_collected.jsonl"
OUT_STATS = BASE / "reply_stats.jsonl"
API = "https://graph.threads.net/v1.0"
FIELDS = "id,text,username,timestamp,is_reply_owned_by_me,replied_to,permalink"
SLEEP = 0.35          # レート制限よけ
MAX_CALLS = 400       # 1回の実行で叩く上限（暴走防止）


def _load_posts(days: int) -> list:
    """直近days日に出した自分の投稿（root_id付き）を新しい順で返す"""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    seen, rows = set(), []
    if not INSIGHTS.exists():
        return rows
    for line in INSIGHTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        rid = d.get("root_id")
        if not rid or rid in seen:
            continue
        if (d.get("date") or "") < cutoff:
            continue
        seen.add(rid)
        rows.append(d)
    rows.sort(key=lambda r: (r.get("date") or "", r.get("slot") or ""), reverse=True)
    return rows


def _known_reply_ids() -> set:
    if not OUT_REPLIES.exists():
        return set()
    ids = set()
    for line in OUT_REPLIES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ids.add(json.loads(line)["id"])
        except Exception:
            pass
    return ids


def collect(days: int = 3):
    token = load_tokens()["access_token"]
    posts = _load_posts(days)
    known = _known_reply_ids()
    new_replies, stats = [], []
    calls = 0

    for p in posts:
        if calls >= MAX_CALLS:
            print(f"[打ち切り] API呼び出しが上限{MAX_CALLS}件に達しました")
            break
        try:
            r = requests.get(f"{API}/{p['root_id']}/conversation",
                             params={"access_token": token, "fields": FIELDS, "limit": 100},
                             timeout=30)
            calls += 1
            time.sleep(SLEEP)
        except Exception as e:
            print(f"[エラー] {p.get('date')} {p.get('slot')}: {e}")
            continue
        if r.status_code != 200:
            print(f"[{r.status_code}] {p.get('date')} {p.get('slot')}: {r.text[:120]}")
            continue

        data = r.json().get("data", [])
        own = [x for x in data if x.get("is_reply_owned_by_me")]
        reader = [x for x in data if not x.get("is_reply_owned_by_me")]

        stats.append({
            "root_id": p["root_id"], "date": p.get("date"), "slot": p.get("slot"),
            "views": p.get("views", 0), "likes": p.get("likes", 0),
            "api_replies": p.get("replies", 0),
            "own_replies": len(own), "reader_replies": len(reader),
        })
        for x in reader:
            if x["id"] in known:
                continue
            known.add(x["id"])
            new_replies.append({
                "id": x["id"], "text": x.get("text", ""),
                "username": x.get("username"), "timestamp": x.get("timestamp"),
                "permalink": x.get("permalink"),
                "root_id": p["root_id"], "post_date": p.get("date"),
                "slot": p.get("slot"), "hook": (p.get("posts") or [""])[0],
            })

    if new_replies:
        with OUT_REPLIES.open("a", encoding="utf-8") as f:
            for x in new_replies:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    if stats:
        with OUT_STATS.open("a", encoding="utf-8") as f:
            for x in stats:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")

    tot_reader = sum(s["reader_replies"] for s in stats)
    tot_own = sum(s["own_replies"] for s in stats)
    tot_likes = sum(s["likes"] for s in stats)
    print(f"対象投稿 {len(stats)}件（直近{days}日・API{calls}回）")
    print(f"  読者からの返信 {tot_reader}件（うち新規 {len(new_replies)}件）")
    print(f"  自分のツリー返信 {tot_own}件 ← 従来これも「返信」に数えられていた")
    print(f"  いいね合計 {tot_likes}件")
    if tot_reader:
        print(f"\n新しく届いた読者の声:")
        for x in new_replies[:20]:
            print(f"  [{x['post_date']} {x['slot']}] @{x['username']}: {x['text'][:80]}")
    return stats, new_replies


def digest(days: int = 30):
    if not OUT_REPLIES.exists():
        print("まだ読者の返信は1件も集まっていません（collect_replies.py を先に実行）")
        return
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = []
    for line in OUT_REPLIES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if (d.get("post_date") or "") >= cutoff:
            rows.append(d)
    if not rows:
        print(f"直近{days}日に読者からの返信はありません")
        return
    print(f"■ 読者の声 {len(rows)}件（直近{days}日）\n")
    by_post = defaultdict(list)
    for d in rows:
        by_post[(d.get("post_date"), d.get("slot"), d.get("hook"))].append(d)
    for (dt, slot, hook), items in sorted(by_post.items(), reverse=True):
        print(f"[{dt} {slot}] {(hook or '')[:44]}")
        for x in items:
            print(f"    @{x['username']}: {x['text']}")
        print()
    users = defaultdict(int)
    for d in rows:
        users[d.get("username")] += 1
    print("■ よく反応してくれる方")
    for u, c in sorted(users.items(), key=lambda x: -x[1])[:10]:
        print(f"    @{u}: {c}件")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    args = sys.argv[1:]
    days = 3
    if "--days" in args:
        days = int(args[args.index("--days") + 1])
    if "--digest" in args:
        digest(days if "--days" in args else 30)
    else:
        collect(days)


if __name__ == "__main__":
    main()
