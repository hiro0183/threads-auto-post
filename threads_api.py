"""
Threads API ラッパー
使い方:
  from threads_api import ThreadsAPI
  api = ThreadsAPI()
  api.post("こんにちは！")
"""

import json
import os
import sys
import requests
from threads_auth import load_tokens, run_auth_flow


class ThreadsAPI:
    BASE = "https://graph.threads.net/v1.0"

    def __init__(self):
        tokens = load_tokens()
        if not tokens:
            print("トークンがありません。認証を開始します...")
            run_auth_flow()
            tokens = load_tokens()
        if not tokens:
            raise RuntimeError("認証に失敗しました")
        self.access_token = tokens["access_token"]
        self.user_id = tokens.get("user_id")

    def _get(self, path: str, params: dict = None) -> dict:
        p = {"access_token": self.access_token, **(params or {})}
        resp = requests.get(f"{self.BASE}{path}", params=p)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict = None) -> dict:
        d = {"access_token": self.access_token, **(data or {})}
        resp = requests.post(f"{self.BASE}{path}", data=d)
        resp.raise_for_status()
        return resp.json()

    # ── 投稿 ──────────────────────────────────────────────

    def post(self, text: str, reply_to_id: str = None, topic_tag: str = None) -> str:
        """テキスト投稿。投稿IDを返す。

        2026-09-13: topic_tag はroot投稿（reply_to_id無し）のときだけ付ける仕様。
        コンテナ作成がtopic_tag付きで失敗した場合、タグ無しで1回だけ再試行する
        （タグの仕様違いで投稿そのものが止まるのを防ぐため）。
        """
        # Step 1: コンテナ作成
        data = {
            "media_type": "TEXT",
            "text": text,
        }
        if reply_to_id:
            data["reply_to_id"] = reply_to_id
        elif topic_tag:
            data["topic_tag"] = topic_tag

        try:
            result = self._post(f"/{self.user_id}/threads", data)
        except Exception as e:
            if not reply_to_id and topic_tag:
                print(f"[WARN] topic_tag付きコンテナ作成に失敗、タグ無しで再試行: {e}")
                data.pop("topic_tag", None)
                result = self._post(f"/{self.user_id}/threads", data)
            else:
                raise
        container_id = result["id"]

        # Step 2: 公開
        pub = self._post(f"/{self.user_id}/threads_publish", {"creation_id": container_id})
        post_id = pub["id"]
        print(f"投稿成功: {post_id}")
        return post_id

    def post_image(self, text: str, image_url: str) -> str:
        """画像付き投稿（画像URLが公開アクセス可能である必要あり）"""
        data = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": text,
        }
        result = self._post(f"/{self.user_id}/threads", data)
        container_id = result["id"]
        pub = self._post(f"/{self.user_id}/threads_publish", {"creation_id": container_id})
        return pub["id"]

    # ── 読み取り ──────────────────────────────────────────

    def get_profile(self) -> dict:
        """自分のプロフィール取得"""
        return self._get(f"/{self.user_id}", {"fields": "id,username,name,biography,followers_count"})

    def get_my_posts(self, limit: int = 10) -> list:
        """自分の投稿一覧"""
        result = self._get(f"/{self.user_id}/threads", {
            "fields": "id,text,timestamp,like_count,reply_count,repost_count",
            "limit": limit,
        })
        return result.get("data", [])

    def get_replies(self, post_id: str) -> list:
        """特定投稿へのリプライ一覧"""
        result = self._get(f"/{post_id}/replies", {
            "fields": "id,text,timestamp,username",
        })
        return result.get("data", [])

    def get_insights(self, post_id: str) -> dict:
        """投稿のインサイト（いいね・リプライ・リポスト数）"""
        result = self._get(f"/{post_id}/insights", {
            "metric": "likes,replies,reposts,quotes,views",
        })
        return result.get("data", [])

    # ── 絡み部門（2026-09-13新設） ──────────────────────────
    # scope threads_keyword_search / threads_profile_discovery が無いと500を返す。
    # 権限が無い間も本番の投稿処理を止めないよう、例外は握って空リスト/Noneで返す。

    def keyword_search(self, q: str, search_type: str = "TOP", limit: int = 25) -> list:
        """キーワード検索（threads_keyword_search scope必須）。失敗時は空リスト。"""
        try:
            result = self._get("/keyword_search", {
                "q": q,
                "search_type": search_type,
                "fields": "id,text,username,timestamp,like_count,reply_count,permalink,media_type",
                "limit": limit,
            })
            return result.get("data", [])
        except Exception as e:
            print(f"[WARN] keyword_search失敗（q={q}）: HTTP {getattr(getattr(e, 'response', None), 'status_code', type(e).__name__)}", file=sys.stderr)
            return []

    def profile_lookup(self, username: str) -> dict | None:
        """公開プロフィール検索（threads_profile_discovery scope必須）。失敗時はNone。"""
        try:
            return self._get("/profile_lookup", {
                "username": username,
                "fields": "id,username,name,threads_biography,follower_count,is_verified",
            })
        except Exception as e:
            print(f"[WARN] profile_lookup失敗（username={username}）: HTTP {getattr(getattr(e, 'response', None), 'status_code', type(e).__name__)}", file=sys.stderr)
            return None

    def get_user_threads(self, user_id: str, limit: int = 10) -> list:
        """他ユーザーの公開投稿（scopeが無ければ空リスト）"""
        try:
            result = self._get(f"/{user_id}/threads", {
                "fields": "id,text,timestamp,like_count,reply_count,permalink",
                "limit": limit,
            })
            return result.get("data", [])
        except Exception as e:
            print(f"[WARN] get_user_threads失敗（user_id={user_id}）: HTTP {getattr(getattr(e, 'response', None), 'status_code', type(e).__name__)}", file=sys.stderr)
            return []


# ── CLI デモ ──────────────────────────────────────────────

if __name__ == "__main__":
    api = ThreadsAPI()

    profile = api.get_profile()
    print(f"\nプロフィール: @{profile.get('username')} ({profile.get('followers_count', '?')}フォロワー)")

    posts = api.get_my_posts(5)
    print(f"\n最新{len(posts)}件の投稿:")
    for p in posts:
        print(f"  [{p['timestamp'][:10]}] {p['text'][:50]}...")

    # テスト投稿（コメントアウト解除で有効化）
    # post_id = api.post("Threadsツールからテスト投稿！")
    # print(f"投稿ID: {post_id}")
