"""
Renderの実測データをリポジトリへ取り込む（2026-08-24新設）

【なぜ「取りに行く」向きにしたか】
従来はRenderがGitHub APIへPersonal Access Token(PAT)でpushしていた。
そのPATが2026-08-21頃に期限切れとなり、同期が401で静かに停止した。
Render側に機密情報を置くのをやめ、公開エンドポイントから取りに来る向きへ変える。
これでトークン失効による沈黙が構造的に無くなる。

【使い方】
  python ingest_render.py                 # 取り込んで sync/ を更新
  python ingest_render.py --base <URL>    # Render URLを指定
  python ingest_render.py --no-write      # 取得して表示するだけ

クラウドルーティン「コンサルThreads 到達率チェック」が毎朝これを実行し、
差分があれば commit / push する。
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent
SYNC_DIR = BASE_DIR / "sync"
DEFAULT_BASE = os.environ.get("RENDER_BASE_URL", "https://threads-auto-post-5f5y.onrender.com")
EXPORT_KEY = os.environ.get("EXPORT_TOKEN", "")

TIMEOUT = 60


def _get(base: str, path: str) -> str:
    url = base.rstrip("/") + path
    if EXPORT_KEY:
        url += ("&" if "?" in url else "?") + "key=" + EXPORT_KEY
    with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8")


def _merge_jsonl(target: Path, incoming: str, key_fn) -> int:
    """既存 + 取得分をキー重複を除いてマージ。追加行数を返す"""
    target.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                seen.add(key_fn(json.loads(line)))
            except Exception:
                continue
    added = []
    for line in incoming.splitlines():
        if not line.strip():
            continue
        try:
            k = key_fn(json.loads(line))
        except Exception:
            continue
        if k in seen:
            continue
        seen.add(k)
        added.append(line)
    if added:
        with open(target, "a", encoding="utf-8") as f:
            for line in added:
                f.write(line + "\n")
    return len(added)


def main():
    base = DEFAULT_BASE
    if "--base" in sys.argv:
        base = sys.argv[sys.argv.index("--base") + 1]
    write = "--no-write" not in sys.argv

    print(f"Render: {base}")

    # 1) 到達率（実際にThreadsへ出たか）
    alert = False
    try:
        status = json.loads(_get(base, "/reach?days=7"))
        y = status.get("yesterday") or {}
        alert = bool(status.get("alert"))
        print(f"到達率: 週 {status.get('week_rate')}% / 前日 {y.get('date')} "
              f"{y.get('actual')}/{y.get('expected')}枠 ({y.get('rate')}%)")
        if alert:
            print(f"[ALERT] 出なかった枠: {', '.join(y.get('missing', []))}"
                  f" / {status.get('miss_streak')}日連続")
        if write:
            (BASE_DIR / "reach_status.json").write_text(
                json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
            print("  reach_status.json を更新")
    except Exception as e:
        print(f"[ERROR] 到達率の取得に失敗: {e}")

    # 2) 実測データ（views等）と投稿ログ・フォロワー
    targets = [
        ("insights_data.jsonl", lambda d: d.get("root_id")),
        ("post_log.jsonl", lambda d: (d.get("timestamp"), d.get("slot"))),
        ("follower_log.jsonl", lambda d: d.get("date")),
    ]
    for name, key_fn in targets:
        try:
            body = _get(base, f"/export/{name}")
        except Exception as e:
            print(f"[ERROR] {name} の取得に失敗: {e}")
            continue
        if not write:
            print(f"  {name}: {len(body.splitlines())}行 取得（書き込みなし）")
            continue
        n = _merge_jsonl(SYNC_DIR / name, body, key_fn)
        print(f"  sync/{name}: {n}件追加")

    print()
    print("ALERT" if alert else "OK")


if __name__ == "__main__":
    main()
