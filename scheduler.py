"""
Render用スケジューラ
Flask Web Service + APScheduler で全スロットを時刻通り自動投稿
- PCに依存しない（クラウド常時稼働）
- misfire_grace_time=60: 遅延60秒以内のみ許容。再起動時に古いスロットを
  再実行しないことで重複投稿を防止する。
- 投稿済みstateはPostgreSQLに永続化（db_state.py）。Render再起動後も維持。
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from db_state import load_posted_state, save_posted_state, is_posted

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def self_ping():
    """Renderのスリープ防止：自分自身のヘルスエンドポイントに10分おきにアクセス"""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    try:
        import requests as req
        req.get(url, timeout=10)
        logger.info("[PING] スリープ防止ping送信")
    except Exception as e:
        logger.warning(f"[PING] ping失敗: {e}")

JST = timezone(timedelta(hours=9))

app = Flask(__name__)


@app.route("/")
def health():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    return jsonify({"status": "running", "time": now})


def post_slot(slot: str):
    """指定スロットを投稿する"""
    from post_runner import (
        get_slot_info,
        load_scheduled_post,
        get_user_id,
        post_thread,
        write_log,
        write_obsidian,
    )
    from token_manager import check_and_refresh
    from content_generator import generate_thread, generate_single_post

    jst_now = datetime.now(JST)
    date_str = jst_now.strftime("%Y-%m-%d")

    # DB（またはファイル）で原子的にチェック → 重複投稿を防止
    if is_posted(date_str, slot):
        logger.info(f"[SKIP] {slot} は既に投稿済み")
        return

    logger.info(f"[START] {slot} 投稿開始 ({jst_now.strftime('%H:%M:%S')} JST)")

    try:
        token = check_and_refresh()
        user_id = get_user_id(token)

        posts = load_scheduled_post(slot)
        if not posts:
            slot_info = get_slot_info(slot)
            if slot_info["type"] == "single":
                posts = generate_single_post()
            else:
                posts = generate_thread(cta=slot_info["cta"])

        post_ids = post_thread(posts, token, user_id)
        write_log(post_ids, posts, "ok", slot=slot)
        write_obsidian(posts, slot)
        save_posted_state(date_str, slot)
        logger.info(f"[OK] {slot} 投稿完了 ({len(post_ids)}件)")

    except Exception as e:
        logger.error(f"[ERROR] {slot} 投稿失敗: {e}", exc_info=True)
        write_log([], [], "error", str(e), slot=slot)


def start_scheduler():
    from post_runner import POST_SCHEDULE

    scheduler = BackgroundScheduler(timezone=JST)

    for slot in POST_SCHEDULE:
        h, m = map(int, slot.split(":"))
        scheduler.add_job(
            post_slot,
            CronTrigger(hour=h, minute=m, timezone=JST),
            args=[slot],
            id=f"post_{slot.replace(':', '')}",
            misfire_grace_time=60,   # 60秒以内の遅延のみ許容。再起動時の古いスロット再実行を防止
            coalesce=True,           # 同一スロットが複数キューに溜まっても1回だけ実行
            max_instances=1,         # 同一スロットの並列実行を禁止
        )

    # スリープ防止ping（10分おき）
    scheduler.add_job(
        self_ping,
        "interval",
        minutes=10,
        id="self_ping",
    )

    scheduler.start()
    logger.info(f"スケジューラ起動完了 ({len(POST_SCHEDULE)}スロット登録)")
    return scheduler


if __name__ == "__main__":
    start_scheduler()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
