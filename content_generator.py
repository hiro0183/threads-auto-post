"""
Claude APIで店舗コンサル・集客・整体院・サロン向けThreadsツリー投稿を生成
各ツリーは3投稿構成:
  1投稿目: 1行キャッチ（常識破壊・感情爆発・ネガティブ訴求・短期的快楽）
  2投稿目: リスト本文（・で箇条書き）
  3投稿目: まとめ＋締め（CTAありの場合はLINE登録へ誘導）
単体投稿: 100文字以下の1投稿
"""

import os
import random
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

THEMES = [
    # 集客
    "新規集客できていない院の本当の原因",
    "紹介が自然に増え続ける院の仕組み",
    "予約が埋まっている院と埋まらない院の決定的な差",
    "口コミが増えない院が無意識にやっていること",
    "来院前に信頼を作る3つの方法",
    "広告費ゼロで月10人新規を取った院のやり方",
    "患者さんの声を最強の集客ツールにする方法",
    # SNS発信
    "Threadsだけで月5人新規を取る方法",
    "フォロワーが増えても集客ゼロな投稿の特徴",
    "バズらなくても集客できる発信の作り方",
    "SNSを毎日更新しているのに結果が出ない理由",
    "Instagram集客で結果が出ない人の共通点",
    "発信が自己満足で終わる人と集客になる人の違い",
    "共感型・数字型・逆説型で投稿が変わる理由",
    "プロフィールを変えただけで問い合わせが増えた院の話",
    "Threadsで逆説型投稿を使うと読まれる理由",
    # ホットペッパー
    "ホットペッパーの掲載料が毎月赤字になる院の特徴",
    "ホットペッパー依存から抜け出した院の共通点",
    "クーポン目当て客しか来ない院が変わるために必要なこと",
    "ホットペッパーをやめた後に伸びた院がやっていたこと",
    # Google・MEO
    "Googleクチコミを自然に増やす声かけの言葉",
    "Googleビジネスプロフィールの放置で損していること",
    "Googleマップで1位になった院がやった3つのこと",
    "MEO対策をやっていない院が毎月こぼしている新規客",
    "口コミ返信で信頼を積み上げる技術",
    # 売上・価格・自費
    "値上げしたら患者が増えた院がやった心理学",
    "売上100万円の壁を超えられない院の共通点",
    "自費メニューを3種類作っていない院が損していること",
    "松竹梅メニューを作ると単価が自然に上がる理由",
    "保険診療だけに頼り続けると5年後に詰まる理由",
    "安売り競争から抜け出せない院長へ",
    "単価を上げずに売上を増やした院の発想",
    "値上げで離れる患者より残る患者の方が大事な理由",
    # 夫婦経営・一人経営
    "夫婦で経営しているのに毎日険悪な院の原因",
    "一人でやっているサロンが燃え尽きる前にすべきこと",
    "孤独な一人院長が経営で詰まる本当の理由",
    "夫婦経営で売上が伸びるチームの作り方",
    "一人経営で年収を上げ続けている先生の共通点",
    # リピート・失客
    "リピートが取れない先生が無意識にやっていること",
    "失客ゼロに近づける再来院の仕組み",
    "3回以内に来なくなる患者さんの本当の理由",
    "施術の見える化をしていない院がリピートを逃す理由",
    # その他
    "開業1年目で廃業する院と生き残る院の違い",
    "LINE公式を使っていない院が毎月こぼしているもの",
    "コンサルに騙されないためのチェックリスト",
    "経営の数字で毎月必ず見るべきもの",
    "スタッフが長続きする院と辞める院の決定的な差",
    "開業3年以内に黒字化する院が最初にやること",
]

CTA_VARIANTS = [
    "僕をフォローしておいてくださいね",
    "LINE登録しておいてくださいね",
    "まず僕をフォローしておいてくださいね",
    "プロフのLINEを登録しておいてくださいね",
    "気になった方はLINE登録しておいてくださいね",
    "続きが気になる方は僕をフォローしておいてくださいね",
    "詳しく話したい方はLINE登録しておいてくださいね",
    "まずLINE登録しておいてくださいね",
]

PROMPT_TREE = """
あなたは整体院・サロンの店舗経営コンサルタントです。
Threadsで毎日発信しており、フォロワーに伴走するスタンスで情報を届けています。

テーマ：「{theme}」

以下のフォーマットでThreadsのツリー投稿を3つ作成してください。

【1投稿目】1行のタイトルのみ。必ず以下のいずれかのアプローチで言い切る。
- 直球タイトル：「1人治療院がつぶれる理由」「リピートが取れない院の共通点」のように主語＋結論を言い切る
- 感情直撃：「もう無理と思ったことがある院長へ」「毎月赤字で怖くないですか」のような感情に刺さる一言
- ネガティブ訴求：「このまま続けると廃業します」「集客しないと来月ヤバいです」のような危機感・恐怖
- 短期的快楽：「今月中に新規5人取れます」「たった1週間で予約が変わりました」のような即効感
- 数字「〇選」形式：「集客が変わる3つの習慣」「潰れる院の共通点5選」のように数字で引っ張る
「実は〇〇」という書き出しは絶対に使わない。1行で言い切ること。改行なし。15〜35文字。

【2投稿目】本文。「〇〇です　その理由」の流れで・（中黒）で箇条書き。3〜6項目。最後に1〜2行の短い橋渡し文を入れる。

【3投稿目】まとめと締め。結論を言い切り、最後は柔らかい言葉で終わる。{cta_line}

【絶対ルール】
- 「。」は使わない
- ハッシュタグは使わない
- 「→」は使わず「・」を使う
- 「"」「"」「"」などダブルクォートは一切使わない
- です・ます調を徹底する
- 命令形は使わない（「してください」はOK）
- 高圧的にならず、伴走・応援スタンスで書く
- ツリー全体で150〜210文字（CTAあり時は最大230文字まで許容）
- 1投稿目は15〜35文字の1行キャッチのみ
- 2投稿目は80〜120文字のリスト
- 3投稿目は40〜70文字のまとめ

出力フォーマット（この区切り文字を必ず使うこと）：

===POST1===
（1投稿目の本文）
===POST2===
（2投稿目の本文）
===POST3===
（3投稿目の本文）
===END===
"""

PROMPT_SINGLE = """
あなたは整体院・サロンの店舗経営コンサルタントです。
Threadsで毎日発信しており、フォロワーに伴走するスタンスで情報を届けています。

テーマ：「{theme}」

1投稿のみ（ツリーなし）で、80文字以内の短い投稿を作成してください。

スタイル：
- 気づき・一言アドバイス・共感・問いかけのいずれか
- 「。」は使わない
- ハッシュタグなし
- です・ます調
- 1〜3行で完結
- 80文字以内厳守

出力フォーマット：
===POST===
（投稿本文）
===END===
"""


def generate_thread(theme: str = None, cta: bool = False, list_style: bool = False) -> list[str]:
    """ツリー投稿3件を生成してリストで返す"""
    if not theme:
        theme = random.choice(THEMES)

    if cta:
        cta_line = f"最後に自然な流れで次のCTAを1行添える：「{random.choice(CTA_VARIANTS)}」"
    else:
        cta_line = ""

    list_style_instruction = "\n【重要】1投稿目は必ず「〇〇 X選」形式（数字＋選）で始めること。例：「集客が変わる3つの習慣」「潰れる院の共通点5選」" if list_style else ""

    prompt = PROMPT_TREE.format(theme=theme, cta_line=cta_line) + list_style_instruction

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    parts = raw.split("===")
    posts = []
    for i, part in enumerate(parts):
        if part.strip() in ("POST1", "POST2", "POST3"):
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            content = content.replace('"', '').replace('\u201c', '').replace('\u201d', '')
            posts.append(content)

    if len(posts) != 3:
        raise ValueError(f"投稿が3件取得できませんでした（{len(posts)}件）\n{raw}")

    return posts


def generate_single_post(theme: str = None) -> list[str]:
    """単体投稿1件を生成してリスト（1要素）で返す"""
    if not theme:
        theme = random.choice(THEMES)

    prompt = PROMPT_SINGLE.format(theme=theme)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    parts = raw.split("===")
    posts = []
    for i, part in enumerate(parts):
        if part.strip() == "POST":
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            content = content.replace('"', '').replace('\u201c', '').replace('\u201d', '')
            posts.append(content)

    if len(posts) != 1:
        raise ValueError(f"単体投稿が取得できませんでした\n{raw}")

    return posts


if __name__ == "__main__":
    print("テスト: ツリー投稿（CTA付き）\n")
    posts = generate_thread(cta=True)
    for i, post in enumerate(posts, 1):
        print(f"--- {i}投稿目 ({len(post)}文字) ---")
        print(post)
        print()

    print("\nテスト: 単体投稿\n")
    post = generate_single_post()
    print(f"--- 単体 ({len(post[0])}文字) ---")
    print(post[0])
