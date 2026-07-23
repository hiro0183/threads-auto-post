"""
GitHubにpost_log.jsonlとinsights_data.jsonlを同期するスクリプト
Render上で実行し、PCがpull_insights.pyで取得できるようにする
"""
import os
import base64
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "hiro0183/threads-auto-post")
GITHUB_API = "https://api.github.com"
BASE_DIR = Path(__file__).parent
JST = timezone(timedelta(hours=9))

SYNC_FILES = [
    (BASE_DIR / "post_log.jsonl", "sync/post_log.jsonl"),
    (BASE_DIR / "insights_data.jsonl", "sync/insights_data.jsonl"),
    # フォロワー推移（2026-07-23追加）。クラウド週次レポートが sync/ 経由で読む
    (BASE_DIR / "follower_log.jsonl", "sync/follower_log.jsonl"),
]


def merge_lines(existing_text: str, local_text: str) -> str:
    """既存(repo)とローカルの行を和集合にする（重複行は除去・既存を先に置いて順序保持）。

    Renderのファイルシステムは揮発性のため、ローカル側は再起動後の“部分”しか持たない。
    既存repo(累積)を土台にローカル分を足すことで、二度と切り詰めずに累積させる（自己修復）。
    JSONLは1行=1レコードで追記のみなので、行単位の完全一致で重複除去すれば安全。
    """
    seen = set()
    out = []
    for block in (existing_text, local_text):
        for line in block.split("\n"):
            line = line.rstrip("\r")
            if not line.strip():
                continue
            if line in seen:
                continue
            seen.add(line)
            out.append(line)
    return "\n".join(out) + "\n" if out else ""


def push_file(local_path: Path, repo_path: str) -> bool:
    if not GITHUB_TOKEN:
        logger.warning("[GITHUB] GITHUB_TOKEN未設定 — スキップ")
        return False
    if not local_path.exists():
        logger.warning(f"[GITHUB] ファイルなし: {local_path}")
        return False

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{repo_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 既存repoファイルを取得（累積のベース）。無ければ空。
    sha = None
    existing_text = ""
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        j = r.json()
        sha = j.get("sha")
        try:
            existing_text = base64.b64decode(j.get("content", "")).decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"[GITHUB] 既存デコード失敗（累積せず上書き扱い）: {e}")
            existing_text = ""

    # 累積マージ（既存 ∪ ローカル・行単位の重複除去）→ 切り詰めない
    local_text = local_path.read_text(encoding="utf-8", errors="replace")
    merged = merge_lines(existing_text, local_text)

    # 内容が変わらなければpushしない（無駄なcommitを防ぐ）
    if merged.strip() == existing_text.strip():
        logger.info(f"[GITHUB] 変更なし（累積済み）: {repo_path}")
        return True

    content_b64 = base64.b64encode(merged.encode("utf-8")).decode()
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    payload = {
        "message": f"sync(累積): {repo_path} ({now_str})",
        "content": content_b64,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload, timeout=30)
    if r.status_code in (200, 201):
        logger.info(f"[GITHUB] push成功(累積): {repo_path}")
        return True
    else:
        logger.error(f"[GITHUB] push失敗: {r.status_code} {r.text[:300]}")
        return False


def sync_all():
    logger.info("[GITHUB] 同期開始")
    for local_path, repo_path in SYNC_FILES:
        push_file(local_path, repo_path)
    logger.info("[GITHUB] 同期完了")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sync_all()
