"""
Claude APIで店舗コンサル・集客・整体院・サロン向けThreadsツリー投稿を生成
各ツリーは3投稿構成:
  1投稿目: タイトルのみ（引っ張る）
  2投稿目: リスト本文（・で箇条書き）
  3投稿目: まとめ＋締め
"""

import os
import random
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

THEMES = [
    "新規集客できない院の共通点",
    "リピートが取れる先生と取れない先生の違い",
    "高額コースが売れる理由",
    "Googleマップで差をつける方法",
    "口コミを自然に増やす方法",
    "LINE公式を使っていない院が損していること",
    "SNS発信が集客に変わる人と変わらない人の違い",
    "値上げを成功させる考え方",
    "カウンセリングで使うべき言葉と使ってはいけない言葉",
    "予約が埋まっている院がやっていること",
    "スタッフが長く続く職場の共通点",
    "紹介が自然に生まれるサロンの仕組み",
    "経営の数字で毎月見るべきもの",
    "開業1年目にやるべきこと",
    "SNSをやるべき理由を迷っている先生へ",
    "価格競争から抜け出す方法",
    "コンサルに騙されないためのチェックリスト",
    "発信が自己満足で終わる人と集客になる人の違い",
    "整体師として長く続けるために大事なこと",
    "院の雰囲気で予約率が変わること",
    "売上100万円が通過点になる院の設計",
    "独立前に準備すべきこと",
    "お客様が「この先生じゃなきゃ」と思う瞬間",
    "経営者がやめるべき習慣",
    "Threadsで信頼を積み上げる投稿パターン",
]

PROMPT_TEMPLATE = """
あなたは整体院・サロンの店舗経営コンサルタントです。
Threadsで毎日発信しており、フォロワーに伴走するスタンスで情報を届けています。

テーマ：「{theme}」

以下のフォーマットでThreadsのツリー投稿を3つ作成してください。

【1投稿目】タイトルのみ。読んだ人が「続きが気になる」と思うキャッチ。1〜2行で完結。

【2投稿目】本文。・（中黒）で箇条書き。3〜6項目。対比がある場合は「〇〇な先生」「〇〇な先生」などで分けてよい。最後に1〜2行の短い橋渡し文を入れる。

【3投稿目】まとめと締め。3〜5行。結論を言い切り、最後は「〜してみてくださいね」「〜できます」など柔らかい言葉で終わる。

【絶対ルール】
- 「。」は使わない
- ハッシュタグは使わない
- 「→」は使わず「・」を使う
- 「"」「"」「"」などダブルクォートは一切使わない
- です・ます調を徹底する
- 命令形は使わない（「してください」はOK、「しろ」「するな」はNG）
- 高圧的にならず、伴走・応援スタンスで書く
- 常識を破るようなキャッチから始める
- ツリー全体（全投稿合計）で150〜200文字に収める（前後多少OK）
- 1投稿目は20〜40文字のキャッチのみ、2投稿目は80〜120文字のリスト、3投稿目は40〜60文字のまとめ

出力フォーマット（この区切り文字を必ず使うこと）：

===POST1===
（1投稿目の本文）
===POST2===
（2投稿目の本文）
===POST3===
（3投稿目の本文）
===END===
"""


def generate_thread(theme: str = None) -> list[str]:
    """ツリー投稿3件を生成してリストで返す"""
    if not theme:
        theme = random.choice(THEMES)

    prompt = PROMPT_TEMPLATE.format(theme=theme)

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # 区切り文字で分割
    parts = raw.split("===")
    posts = []
    for i, part in enumerate(parts):
        if part.strip() in ("POST1", "POST2", "POST3"):
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            posts.append(content)

    if len(posts) != 3:
        raise ValueError(f"投稿が3件取得できませんでした（{len(posts)}件）\n{raw}")

    return posts


if __name__ == "__main__":
    print("テスト: ツリー投稿3件生成\n")
    posts = generate_thread()
    for i, post in enumerate(posts, 1):
        print(f"--- {i}投稿目 ---")
        print(post)
        print(f"（{len(post)}文字）\n")
