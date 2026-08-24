"""
GitHubのsync/フォルダからpost_log.jsonlとinsights_data.jsonlを取得してローカルにマージ
Renderがpushした内容をPCで引き取る用

2026-08-24: GitHub API + Personal Access Token（PAT）での取得を廃止し、git経由に変更。
  旧方式はPATが2026-08-21頃に期限切れとなり401で静かに失敗し、post_log.jsonlが
  8/3で止まり、そこを起点にしていたインサイト集計まで連鎖的に停止した（実測が3週間凍結）。
  gitの認証情報はCredential Managerが保持しており別系統のため、この経路なら巻き込まれない。

使い方:
  python pull_insights.py          # マージ後に自動でinsights集計も実行
  python pull_insights.py --no-collect  # マージのみ（集計しない）
"""
import sys
import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent


def fetch_repo_file(repo_path: str) -> bytes | None:
    """origin/master の最新内容をgit経由で読む（PAT不要・作業ツリーを汚さない）"""
    try:
        subprocess.run(
            ["git", "fetch", "origin", "master"],
            cwd=BASE_DIR, check=True, capture_output=True, timeout=120,
        )
        r = subprocess.run(
            ["git", "show", f"origin/master:{repo_path}"],
            cwd=BASE_DIR, check=True, capture_output=True, timeout=120,
        )
        return r.stdout
    except Exception as e:
        print(f"[ERROR] {repo_path} 取得失敗: {e}")
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

    print("GitHub(origin/master)からデータ取得中...")

    data = fetch_repo_file("sync/post_log.jsonl")
    if data:
        added = merge_post_log(data)
        print(f"post_log.jsonl: {added}件追加")
    else:
        print("post_log.jsonl: スキップ（まだGitHubに存在しない可能性あり）")

    data = fetch_repo_file("sync/insights_data.jsonl")
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
