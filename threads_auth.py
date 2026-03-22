"""
Threads OAuth 認証ツール
使い方:
  1. python threads_auth.py
  2. 表示されたURLをブラウザで開く
  3. Threadsでログイン・認証
  4. アクセストークンが取得される
"""

import os
import json
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.environ["THREADS_APP_ID"]
APP_SECRET = os.environ["THREADS_APP_SECRET"]
REDIRECT_URI = os.environ.get("THREADS_REDIRECT_URI", "http://localhost:5000/callback")
PORT = 5000

# 必要なスコープ（投稿・読み取り）
SCOPES = "threads_basic,threads_content_publish,threads_read_replies,threads_manage_replies,threads_manage_insights"

TOKEN_FILE = "tokens.json"


class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # サーバーログを抑制

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        if "error" in params:
            error = params["error"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h1>エラー: {error}</h1>".encode())
            self.server.auth_code = None
            return

        code = params.get("code", [None])[0]
        if not code:
            self.send_response(400)
            self.end_headers()
            return

        self.server.auth_code = code

        # コードをトークンに交換
        token_data = exchange_code_for_token(code)
        if token_data:
            save_tokens(token_data)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <h1>✅ 認証成功！</h1>
            <p>アクセストークンを取得しました。このウィンドウを閉じてください。</p>
            <script>setTimeout(() => window.close(), 2000);</script>
            """
            self.wfile.write(html.encode())
        else:
            self.send_response(500)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h1>❌ トークン取得失敗</h1>".encode())


def exchange_code_for_token(code: str) -> dict | None:
    """認証コードを短期トークンに交換"""
    resp = requests.post(
        "https://graph.threads.net/oauth/access_token",
        data={
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
    )
    if resp.status_code != 200:
        print(f"トークン交換エラー: {resp.text}")
        return None

    short_token = resp.json()
    print(f"短期トークン取得: {short_token}")

    # 長期トークンに交換（60日間有効）
    long_resp = requests.get(
        "https://graph.threads.net/access_token",
        params={
            "grant_type": "th_exchange_token",
            "client_secret": APP_SECRET,
            "access_token": short_token["access_token"],
        },
    )
    if long_resp.status_code == 200:
        long_token = long_resp.json()
        long_token["user_id"] = short_token.get("user_id")
        print(f"長期トークン取得成功（{long_token.get('expires_in', '?')}秒間有効）")
        return long_token

    print(f"長期トークン交換失敗、短期トークンを使用: {long_resp.text}")
    return short_token


def save_tokens(token_data: dict):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"トークンを {TOKEN_FILE} に保存しました")


def load_tokens() -> dict | None:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def get_auth_url() -> str:
    params = urlencode({
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "response_type": "code",
    })
    return f"https://threads.net/oauth/authorize?{params}"


def run_auth_flow():
    auth_url = get_auth_url()
    print(f"\n認証URLを開いています...\n{auth_url}\n")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", PORT), CallbackHandler)
    server.auth_code = None
    print(f"コールバック待機中: http://localhost:{PORT}/callback")
    server.handle_request()

    if server.auth_code:
        print("\n認証完了！")
    else:
        print("\n認証失敗")


if __name__ == "__main__":
    existing = load_tokens()
    if existing:
        print(f"既存のトークンを検出: user_id={existing.get('user_id')}")
        choice = input("再認証しますか？ (y/N): ").strip().lower()
        if choice != "y":
            print("既存のトークンを使用します")
            exit(0)

    run_auth_flow()
