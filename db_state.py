"""
投稿済みstateのPostgreSQL永続化モジュール

Render上ではDATABASE_URLが設定されている場合はDBを使用。
未設定の場合はファイルベース（ローカル開発用）にフォールバック。

テーブル（初回自動作成）:
  posted_slots (date DATE, slot VARCHAR(5), posted_at TIMESTAMPTZ)
  PRIMARY KEY (date, slot)
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent
STATE_DIR = BASE_DIR / "state"

# ── DB接続 ────────────────────────────────────────────────

def _get_conn():
    """PostgreSQL接続を返す。DATABASE_URL未設定はNoneを返す"""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    try:
        import psycopg2
        # RenderのURLは postgres:// → psycopg2は postgresql:// が必要
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    except Exception as e:
        logger.error(f"[DB] 接続失敗 → ファイルにフォールバック: {e}")
        return None


def _ensure_table(conn):
    """テーブルが存在しない場合は作成する"""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posted_slots (
                date    DATE        NOT NULL,
                slot    VARCHAR(5)  NOT NULL,
                posted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (date, slot)
            )
        """)
    conn.commit()


# ── 公開API ───────────────────────────────────────────────

def load_posted_state(date_str: str) -> set:
    """投稿済みスロットのセットを返す（DB優先、フォールバックはファイル）"""
    conn = _get_conn()
    if conn:
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT slot FROM posted_slots WHERE date = %s",
                    (date_str,),
                )
                rows = cur.fetchall()
            return {row[0] for row in rows}
        except Exception as e:
            logger.error(f"[DB] load失敗 → ファイルにフォールバック: {e}")
        finally:
            conn.close()

    # ── ファイルフォールバック ──
    state_file = STATE_DIR / f"{date_str}.json"
    if not state_file.exists():
        return set()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    return set(data.get("posted", []))


def save_posted_state(date_str: str, slot: str):
    """投稿済みスロットを記録する（DB優先、フォールバックはファイル）"""
    conn = _get_conn()
    if conn:
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                # INSERT OR IGNORE 相当：重複は無視
                cur.execute(
                    """
                    INSERT INTO posted_slots (date, slot, posted_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (date, slot) DO NOTHING
                    """,
                    (date_str, slot),
                )
            conn.commit()
            logger.info(f"[DB] {date_str} {slot} を投稿済みとして記録")
            return
        except Exception as e:
            logger.error(f"[DB] save失敗 → ファイルにフォールバック: {e}")
        finally:
            conn.close()

    # ── ファイルフォールバック ──
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{date_str}.json"
    posted = load_posted_state(date_str)
    posted.add(slot)
    data = {
        "posted": sorted(posted),
        "updated": datetime.now(JST).isoformat(),
    }
    state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_posted(date_str: str, slot: str) -> bool:
    """指定スロットが投稿済みかどうかを返す（原子的チェック）"""
    conn = _get_conn()
    if conn:
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM posted_slots WHERE date = %s AND slot = %s",
                    (date_str, slot),
                )
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"[DB] is_posted失敗 → ファイルにフォールバック: {e}")
        finally:
            conn.close()

    return slot in load_posted_state(date_str)
