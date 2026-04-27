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
]


def push_file(local_path: Path, repo_path: str) -> bool:
    if not GITHUB_TOKEN:
        logger.warning("[GITHUB] GITHUB_TOKEN未設定 — スキップ")
        return False
    if not local_path.exists():
        logger.warning(f"[GITHUB] ファイルなし: {local_path}")
        return False

    content_b64 = base64.b64encode(local_path.read_bytes()).decode()
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{repo_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    sha = None
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        sha = r.json().get("sha")

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    payload = {
        "message": f"sync: {repo_path} ({now_str})",
        "content": content_b64,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload, timeout=30)
    if r.status_code in (200, 201):
        logger.info(f"[GITHUB] push成功: {repo_path}")
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
