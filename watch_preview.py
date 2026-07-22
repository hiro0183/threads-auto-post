"""
「Threads投稿プレビュー」フォルダの .txt を監視し、
保存されたら自動で posts/{date}.json に反映するスクリプト

PC起動時にタスクスケジューラから自動起動される
"""

import re
import json
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"
DESKTOP = Path.home() / "OneDrive" / "Desktop" / "Threads_Preview"

logging.basicConfig(
    filename=BASE_DIR / "watch.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)


def parse_txt(txt_path: Path) -> dict:
    text = txt_path.read_text(encoding="utf-8")
    schedule = {}

    blocks = re.split(r"\n(?=【\d{2}:\d{2}】)", text)

    for block in blocks:
        time_match = re.match(r"【(\d{2}:\d{2})】", block)
        if not time_match:
            continue
        slot = time_match.group(1)

        body = re.sub(r"^【\d{2}:\d{2}】.*\n", "", block)
        body = re.sub(r"^-{3,}.*\n", "", body, flags=re.MULTILINE)
        body = body.strip()

        if not body:
            continue

        if "▼ 1投稿目" in body:
            posts = []
            parts = re.split(r"▼ \d+投稿目\n?", body)
            for part in parts:
                part = part.strip()
                if part:
                    posts.append(part)
            schedule[slot] = posts
        else:
            schedule[slot] = [body]

    return schedule


def git_push(json_file: Path, date_str: str):
    """更新したJSONをGitHubにpushしてRenderに反映させる"""
    import subprocess
    try:
        subprocess.run(["git", "add", str(json_file)], cwd=BASE_DIR, check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=BASE_DIR
        )
        if result.returncode == 0:
            logging.info(f"[GIT] 変更なし（{date_str}）")
            return
        subprocess.run(
            ["git", "commit", "-m", f"preview edit: {date_str}"],
            cwd=BASE_DIR, check=True
        )
        subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
        msg = f"[GIT] push完了 → Renderに反映中（{date_str}）"
        print(msg)
        logging.info(msg)
    except Exception as e:
        logging.error(f"[GIT] push失敗: {e}")


def apply_txt(txt_path: Path):
    date_str = txt_path.stem
    if not re.match(r"\d{4}-\d{2}-\d{2}", date_str):
        return

    try:
        schedule = parse_txt(txt_path)
        if not schedule:
            return

        POSTS_DIR.mkdir(exist_ok=True)
        out_file = POSTS_DIR / f"{date_str}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)

        msg = f"反映完了: {date_str}.txt → {out_file}（{len(schedule)}スロット）"
        print(msg)
        logging.info(msg)

        git_push(out_file, date_str)

    except Exception as e:
        logging.error(f"エラー: {txt_path.name} → {e}")


class TxtHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".txt"):
            time.sleep(0.5)  # 保存完了を少し待つ
            apply_txt(Path(event.src_path))

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".txt"):
            time.sleep(0.5)
            apply_txt(Path(event.src_path))


def main():
    DESKTOP.mkdir(parents=True, exist_ok=True)
    print(f"監視開始: {DESKTOP}")
    logging.info(f"監視開始: {DESKTOP}")

    observer = Observer()
    observer.schedule(TxtHandler(), str(DESKTOP), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
