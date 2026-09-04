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
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from db_state import load_posted_state, save_posted_state, is_posted, try_reserve_slot

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


ALLOWED_EXPORTS = {
    "post_log.jsonl",
    "insights_data.jsonl",
    "follower_log.jsonl",
    "insights_collected.jsonl",
}


def _export_authorized() -> bool:
    """EXPORT_TOKEN が設定されていれば ?key= の一致を要求する（未設定なら誰でも可）"""
    from flask import request
    expected = os.environ.get("EXPORT_TOKEN")
    return (not expected) or request.args.get("key") == expected


@app.route("/export/<name>")
def export_file(name: str):
    """Renderのディスク上の実測データをHTTPで渡す（2026-08-24新設）。

    従来はRenderからGitHub APIへPATでpushしていたが、PATが2026-08-21頃に
    期限切れとなり同期が静かに停止した。取りに来てもらう向きに変えることで、
    Render側から機密情報（PAT）を無くし、失効による沈黙をなくす。
    クラウドルーティンがこれを取得してリポジトリへcommitする。
    """
    from flask import Response
    if not _export_authorized():
        return jsonify({"error": "unauthorized"}), 401
    if name not in ALLOWED_EXPORTS:
        return jsonify({"error": "not found"}), 404
    path = Path(__file__).parent / name
    if not path.exists():
        return Response("", mimetype="text/plain")
    return Response(path.read_text(encoding="utf-8"), mimetype="text/plain")


@app.route("/reach")
def reach():
    """到達率（実際にThreadsへ出た枠 ÷ 予定枠）を返す（2026-08-24新設）。

    ファイルの存在ではなくThreads APIの実投稿を正として測る唯一の窓口。
    """
    if not _export_authorized():
        return jsonify({"error": "unauthorized"}), 401
    try:
        days = int(request.args.get("days", 7))
    except Exception:
        days = 7
    try:
        import reach_check
        return jsonify(reach_check.build_status(days=max(1, min(days, 30))))
    except Exception as e:
        logger.error(f"[REACH] 算出失敗: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def reach_job():
    """毎朝7:00 — 前日の到達率を測り、100%未満ならログに残す"""
    logger.info("[REACH] 到達率チェック開始")
    try:
        import reach_check
        status = reach_check.build_status(days=7)
        reach_check.save_status(status)
        y = status.get("yesterday") or {}
        if status.get("alert"):
            logger.error(
                f"[REACH][ALERT] 前日 {y.get('date')} の到達率 {y.get('rate')}%"
                f"（{y.get('actual')}/{y.get('expected')}枠）"
                f" 出なかった枠: {','.join(y.get('missing', []))}"
                f" / {status.get('miss_streak')}日連続"
            )
        else:
            logger.info(f"[REACH] 前日 {y.get('date')} は100%達成（{y.get('actual')}枠）")
    except Exception as e:
        logger.error(f"[REACH] チェック失敗: {e}", exc_info=True)


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

    jst_now = datetime.now(JST)
    date_str = jst_now.strftime("%Y-%m-%d")

    # ★原稿が無いときは投稿しない（2026-07-28）
    # 以前はここで content_generator の緊急生成にフォールバックしていたが、
    #   ・週次プランも品質ゲートも通っていない本文がそのまま出る
    #   ・旧テーマ・旧ルール（禁止したはずの疑問形フック等）で書かれる
    #   ・この経路だけ Anthropic API 直叩きで課金が発生する
    # という三重の事故になる（2026-07-27にコンサル垢で11本発動）。
    # 出さずに穴を空け、司令室と post_log に理由を残す方を選ぶ。
    posts = load_scheduled_post(slot)
    if not posts:
        logger.error(
            f"[NO-DRAFT] {slot} は原稿 posts/{date_str}.json が無い（または空）ため投稿しません。"
            " 検品を通っていない緊急生成は行わない方針"
        )
        write_log([], [], "error", "原稿なし（無検品の緊急生成を回避してスキップ）", slot=slot)
        return

    # 投稿前にDBへ原子的にINSERT → 重複投稿をDBレベルで防止
    # try_reserve_slot は ON CONFLICT DO NOTHING なので複数スレッド/プロセスでも安全
    if not try_reserve_slot(date_str, slot):
        logger.info(f"[SKIP] {slot} は既に予約済み・投稿済み")
        return

    logger.info(f"[START] {slot} 投稿開始 ({jst_now.strftime('%H:%M:%S')} JST)")

    try:
        token = check_and_refresh()
        user_id = get_user_id(token)

        post_ids = post_thread(posts, token, user_id)
        write_log(post_ids, posts, "ok", slot=slot)
        write_obsidian(posts, slot)
        # save_posted_state は try_reserve_slot でINSERT済みのため不要
        logger.info(f"[OK] {slot} 投稿完了 ({len(post_ids)}件)")

    except Exception as e:
        logger.error(f"[ERROR] {slot} 投稿失敗: {e}", exc_info=True)
        write_log([], [], "error", str(e), slot=slot)


def collect_insights_job():
    """毎朝6:05 — 前日までの投稿インサイトを集計してGitHubに同期"""
    logger.info("[INSIGHTS] インサイト集計開始")
    try:
        import collect_insights
        collect_insights.main()
    except Exception as e:
        logger.error(f"[INSIGHTS] 集計失敗: {e}", exc_info=True)


def collect_replies_job():
    """毎朝6:20 — 読者からの返信を集める（2026-09-04新設）

    Threads APIの replies には自分のツリー2〜3投稿目が含まれるため、
    own/reader を分けて記録する。読者の生の言葉は投稿リサーチの材料になる。
    """
    logger.info("[REPLIES] 読者返信の収集開始")
    try:
        import collect_replies
        collect_replies.collect(days=3)
    except Exception as e:
        logger.error(f"[REPLIES] 収集失敗: {e}", exc_info=True)


def track_followers_job():
    """毎朝6:10 — フォロワー数を記録（2026-07-23にローカルPCから移管）"""
    logger.info("[FOLLOWERS] フォロワー数の記録開始")
    try:
        import track_followers
        track_followers.main()
    except Exception as e:
        logger.error(f"[FOLLOWERS] 記録失敗: {e}", exc_info=True)


def github_sync_job():
    """毎晩23:30 — post_log.jsonlとinsights_data.jsonlをGitHubにpush"""
    logger.info("[GITHUB] 同期ジョブ開始")
    try:
        from github_sync import sync_all
        sync_all()
    except Exception as e:
        logger.error(f"[GITHUB] 同期失敗: {e}", exc_info=True)


def recover_missed_slots():
    """起動時に今日の未投稿スロットを回収して順次実行する（Render再起動対策）"""
    import threading
    import time as _time
    from post_runner import POST_SCHEDULE
    from db_state import is_posted

    jst_now = datetime.now(JST)
    date_str = jst_now.strftime("%Y-%m-%d")
    current_hm = jst_now.strftime("%H:%M")

    missed = [s for s in POST_SCHEDULE if s < current_hm and not is_posted(date_str, s)]
    if not missed:
        logger.info("[RECOVER] 未投稿スロットなし")
        return

    logger.info(f"[RECOVER] {len(missed)}件の未投稿スロットを順次実行: {missed}")

    def _run():
        for slot in missed:
            try:
                post_slot(slot)
            except Exception as e:
                logger.error(f"[RECOVER] {slot} 失敗: {e}", exc_info=True)
            _time.sleep(10)  # スロット間に10秒待機してAPI負荷を分散

    threading.Thread(target=_run, daemon=True).start()


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
            misfire_grace_time=60,
            coalesce=True,
            max_instances=1,
        )

    # スリープ防止ping（10分おき）
    scheduler.add_job(
        self_ping,
        "interval",
        minutes=10,
        id="self_ping",
    )

    # インサイト集計（毎朝6:05）
    scheduler.add_job(
        collect_insights_job,
        CronTrigger(hour=6, minute=5, timezone=JST),
        id="collect_insights",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # 読者返信の収集（毎朝6:20・2026-09-04新設）
    # get_replies() は前からあったのに一度も呼ばれていなかった。
    # 読者の生の言葉＝投稿リサーチの材料を毎日ためる。
    scheduler.add_job(
        collect_replies_job,
        CronTrigger(hour=6, minute=20, timezone=JST),
        id="collect_replies",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # フォロワー数の記録（毎朝6:10・2026-07-23にローカルPCから移管）
    scheduler.add_job(
        track_followers_job,
        CronTrigger(hour=6, minute=10, timezone=JST),
        id="track_followers",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # 到達率チェック（毎朝7:00・2026-08-24新設）
    # 「原稿があるか」ではなく「実際に出たか」を毎日みる唯一の監視。
    scheduler.add_job(
        reach_job,
        CronTrigger(hour=7, minute=0, timezone=JST),
        id="reach_check",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # GitHub同期（毎晩23:30）
    scheduler.add_job(
        github_sync_job,
        CronTrigger(hour=23, minute=30, timezone=JST),
        id="github_sync",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info(f"スケジューラ起動完了 ({len(POST_SCHEDULE)}スロット登録 + insights/sync)")

    # 起動時に未投稿スロットを回収（Render再起動後の取りこぼし対策）
    recover_missed_slots()

    return scheduler


if __name__ == "__main__":
    start_scheduler()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
