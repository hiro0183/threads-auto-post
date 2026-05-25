"""
GitHubのsync/フォルダからpost_log.jsonlとinsights_data.jsonlを取得してローカルにマージ
Renderが23:30にpushした内容を翌朝PCで引き取る用

使い方:
  python pull_insights.py          # マージ後に自動でinsights集計も実行
  python pull_insights.py --no-collect  # マージのみ（集計しない）
"""
import os
import sys
import json
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "hiro0183/threads-auto-post")
GITHUB_API = "https://api.github.com"
BASE_DIR = Path(__file__).parent


def fetch_github_file(repo_path: str) -> bytes | None:
    if not GITHUB_TOKEN:
        print("[ERROR] .envにGITHUB_TOKENを設定してください")
        return None
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{repo_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        return base64.b64decode(r.json().get("content", ""))
    else:
        print(f"[ERROR] {repo_path} 取得失敗: {r.status_code}")
        return None


def merge_post_log(remote_content: bytes) -> int:
    local_path = BASE_DIR / "post_log.jsonl"
    existing_ids = set()
    if local_path.exists():
        for line in local_path.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            try:
                d = json.loads(line)
                ids = d.get("post_ids", [])
                if ids:
                    existing_ids.add(ids[0])
            except Exception:
                pass

    new_lines = []
    for line in remote_content.decode("utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            d = json.loads(line)
            ids = d.get("post_ids", [])
            key = ids[0] if ids else None
            if key and key not in existing_ids:
                existing_ids.add(key)
                new_lines.append(line)
        except Exception:
            pass

    if new_lines:
        with open(local_path, "a", encoding="utf-8") as f:
            for line in new_lines:
                f.write(line + "\n")
    return len(new_lines)


def merge_insights_data(remote_content: bytes) -> int:
    local_path = BASE_DIR / "insights_data.jsonl"
    existing_ids = set()
    if local_path.exists():
        for line in local_path.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            try:
                d = json.loads(line)
                key = d.get("root_id")
                if key:
                    existing_ids.add(key)
            except Exception:
                pass

    new_lines = []
    for line in remote_content.decode("utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            d = json.loads(line)
            key = d.get("root_id")
            if key and key not in existing_ids:
                existing_ids.add(key)
                new_lines.append(line)
        except Exception:
            pass

    if new_lines:
        with open(local_path, "a", encoding="utf-8") as f:
            for line in new_lines:
                f.write(line + "\n")
    return len(new_lines)


def main():
    no_collect = "--no-collect" in sys.argv

    print("GitHubからデータ取得中...")

    data = fetch_github_file("sync/post_log.jsonl")
    if data:
        added = merge_post_log(data)
        print(f"post_log.jsonl: {added}件追加")
    else:
        print("post_log.jsonl: スキップ（まだGitHubに存在しない可能性あり）")

    data = fetch_github_file("sync/insights_data.jsonl")
    if data:
        added = merge_insights_data(data)
        print(f"insights_data.jsonl: {added}件追加")
    else:
        print("insights_data.jsonl: スキップ（まだGitHubに存在しない可能性あり）")

    if not no_collect:
        print("\nインサイト集計を実行中...")
        import collect_insights
        collect_insights.main()

        print("\nダッシュボード更新中...")
        try:
            import generate_dashboard
            generate_dashboard.main()
        except Exception as e:
            print(f"[WARN] ダッシュボード更新失敗: {e}")
    else:
        print("\n--no-collect 指定のため集計・ダッシュボードはスキップ")


if __name__ == "__main__":
    main()
