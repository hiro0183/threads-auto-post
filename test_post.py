import os, requests
from dotenv import load_dotenv
load_dotenv()

token = os.environ["THREADS_ACCESS_TOKEN"]

# ユーザーID取得
r = requests.get("https://graph.threads.net/v1.0/me", params={"fields": "id,username", "access_token": token})
print(r.json())
user_id = r.json()["id"]

# コンテナ作成
r2 = requests.post(f"https://graph.threads.net/v1.0/{user_id}/threads",
    data={"media_type": "TEXT", "text": "テスト", "access_token": token})
print(r2.json())
container_id = r2.json()["id"]

# 公開
r3 = requests.post(f"https://graph.threads.net/v1.0/{user_id}/threads_publish",
    data={"creation_id": container_id, "access_token": token})
print(r3.json())
print("投稿完了！")
