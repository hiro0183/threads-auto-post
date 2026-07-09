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
        return psycopg2.connect(url, sslmode="require", connect_timeout=15)
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


def try_reserve_slot(date_str: str, slot: str) -> bool:
    """スロットを原子的に予約してTrueを返す。既に予約済みならFalseを返す。

    is_posted() → post() → save() の間に別スレッド/プロセスが割り込む
    TOCTOU競合を防ぐため、投稿前にこの関数でDBを先に確保する。
    INSERT ON CONFLICT はDB側で排他制御されるので複数プロセスでも安全。
    """
    conn = _get_conn()
    if conn:
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO posted_slots (date, slot, posted_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (date, slot) DO NOTHING
                    """,
                    (date_str, slot),
                )
                reserved = cur.rowcount == 1
            conn.commit()
            return reserved
        except Exception as e:
            logger.error(f"[DB] try_reserve失敗 → スキップ扱いで安全側に倒す: {e}")
            return False
        finally:
            conn.close()

    # ファイルフォールバック（ローカル開発用）
    if slot in load_posted_state(date_str):
        return False
    return True


# ── Threadsトークン永続化 ─────────────────────────────────
# Renderのファイルシステムは再デプロイで消えるため、tokens.jsonだけだと
# 自動リフレッシュした値が翌日には巻き戻り、.envの種トークンが60日で失効する。
# トークンもDBに置くことで、リフレッシュ済みの値が再デプロイをまたいで残る（実質無期限）。
# expires_at/refreshed_at はTEXTで保存（token_manager側のnaive ISO文字列をそのまま往復させ、
# タイムゾーン変換による日付計算のズレを避ける）。

def _ensure_token_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS threads_token (
                id           INT PRIMARY KEY DEFAULT 1,
                access_token TEXT        NOT NULL,
                token_type   TEXT,
                user_id      TEXT,
                expires_at   TEXT,
                refreshed_at TEXT,
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT single_row CHECK (id = 1)
            )
        """)
    conn.commit()


def load_token_from_db() -> dict | None:
    """DBからトークンを読む。DATABASE_URL未設定・行なし・失敗はNone"""
    conn = _get_conn()
    if not conn:
        return None
    try:
        _ensure_token_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT access_token, token_type, user_id, expires_at, refreshed_at "
                "FROM threads_token WHERE id = 1"
            )
            row = cur.fetchone()
        if not row or not row[0]:
            return None
        data = {"access_token": row[0]}
        if row[1]:
            data["token_type"] = row[1]
        if row[2]:
            data["user_id"] = row[2]
        if row[3]:
            data["expires_at"] = row[3]
        if row[4]:
            data["refreshed_at"] = row[4]
        return data
    except Exception as e:
        logger.error(f"[DB] load_token失敗: {e}")
        return None
    finally:
        conn.close()


def save_token_to_db(data: dict) -> bool:
    """トークンをDBに保存（単一行・上書き）。成功でTrue、DB無し/失敗でFalse"""
    conn = _get_conn()
    if not conn:
        return False
    try:
        _ensure_token_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO threads_token
                    (id, access_token, token_type, user_id, expires_at, refreshed_at, updated_at)
                VALUES (1, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    token_type   = EXCLUDED.token_type,
                    user_id      = EXCLUDED.user_id,
                    expires_at   = EXCLUDED.expires_at,
                    refreshed_at = EXCLUDED.refreshed_at,
                    updated_at   = NOW()
                """,
                (
                    data.get("access_token"),
                    data.get("token_type"),
                    data.get("user_id"),
                    data.get("expires_at"),
                    data.get("refreshed_at"),
                ),
            )
        conn.commit()
        logger.info("[DB] Threadsトークンを保存しました")
        return True
    except Exception as e:
        logger.error(f"[DB] save_token失敗: {e}")
        return False
    finally:
        conn.close()
