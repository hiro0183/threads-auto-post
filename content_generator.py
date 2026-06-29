"""
Claude APIで整体院・整骨院・サロン経営者向けThreadsツリー投稿を生成
発信者は「ヒロ先生」＝パソコン苦手だったアラフィフ院長が、AIで月商300万を達成し
同業の経営者に伴走するスタンス。経営ネタとAI×経営ネタを同じ軸で発信する。
各ツリーは3投稿構成:
  1投稿目: 1行キャッチ（常識破壊・感情爆発・ネガティブ訴求・短期的快楽）
  2投稿目: リスト本文（・で箇条書き）
  3投稿目: まとめ＋締め（CTAありの場合はLINE登録へ誘導）
単体投稿: 100文字以下の1投稿
"""

import os
import json
import random
import anthropic
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

BASE_DIR = Path(__file__).parent
INSIGHTS_DATA_FILE = BASE_DIR / "insights_data.jsonl"
POST_LOG_FILE = BASE_DIR / "post_log.jsonl"

JST = timezone(timedelta(hours=9))

# 7時台・優先スロット（最重要時間帯）
PRIORITY_SLOTS = {"07:00", "07:30"}

# 優先スロット用テーマ（7時台・最重要時間帯）
PRIORITY_THEMES = [
    "月商150万でスタッフ雇った先生が半年で閉院した理由",
    "値上げしたのに患者が増えた院が先にやった1つのこと",
    "単価を上げても患者が離れない院がやっていること",
    "新規を追うほど売上が不安定になる理由",
    "リピート率96%の院が初回でやっていること",
    "廃業した院長に共通していた習慣",
    "月商が100万で止まる院が時間を使っている場所",
    "月商300万で週休3日、その仕組みの正体",
    "集客より先に整えるべきもの",
    "初回で通院プランを出さない院の継続率が低い理由",
    "高単価が売れない院が説明で失敗している場所",
    "売上は増えているのに手残りが減る院の構造",
]


def load_used_catches(days: int = 7) -> list[str]:
    """過去N日間の投稿1行目を返す（重複防止用）"""
    if not POST_LOG_FILE.exists():
        return []
    cutoff = datetime.now(JST) - timedelta(days=days)
    catches = []
    for line in POST_LOG_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("status") != "ok":
                continue
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=JST)
            if ts < cutoff:
                continue
            posts = entry.get("posts", [])
            if posts:
                catches.append(posts[0][:60].replace("\n", " "))
        except Exception:
            pass
    return catches


def _eng_rate(r: dict) -> float:
    v = r.get("views", 0) or 0
    if v == 0:
        return 0.0
    eng = sum(r.get(m, 0) or 0 for m in ["likes", "replies", "reposts", "quotes"])
    return eng / v * 100


def _load_top_patterns(top_n: int = 10) -> str:
    """インサイトデータから上位投稿のパターンを返す（エンゲージ率上位全文＋Views上位キャッチ）"""
    if not INSIGHTS_DATA_FILE.exists():
        return ""
    rows = []
    seen = set()
    for line in INSIGHTS_DATA_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            r = json.loads(line)
            rid = r.get("root_id", "")
            if rid in seen:
                continue
            seen.add(rid)
            if isinstance(r.get("views"), int) and (r.get("views") or 0) > 0:
                rows.append(r)
        except Exception:
            pass
    if not rows:
        return ""

    top_views = sorted(rows, key=lambda x: x["views"], reverse=True)[:top_n]
    top_eng = sorted(rows, key=lambda x: _eng_rate(x), reverse=True)[:3]

    lines = ["【参考：過去に伸びた投稿の冒頭（型の構造のみ参考にすること）】"]
    lines.append("")

    # エンゲージ率上位の冒頭1行のみ（真似ではなく型の構造の参考に留める）
    lines.append("▼ エンゲージ率上位投稿の冒頭（型の構造を参考にする・言葉やフックは真似せず、今回のテーマに合わせて新しく書くこと）")
    for i, r in enumerate(top_eng, 1):
        er = round(_eng_rate(r), 1)
        posts = r.get("posts", [])
        first_line = posts[0][:60] if posts else r.get("catch", "")[:60]
        lines.append(f"[{i}位] エンゲージ率{er}% / Views {r.get('views',0):,}")
        lines.append(f"  冒頭: {first_line}{'…' if posts and len(posts[0]) > 60 else ''}")
    lines.append("")

    # Views上位のキャッチ（言葉選びの参考）
    catches = [r.get("catch", "") for r in top_views if r.get("catch")]
    if catches:
        lines.append("▼ Views上位投稿の1投稿目（フックの型の参考）")
        for c in catches:
            lines.append(f"・{c}")
        lines.append("")
        lines.append("※型の構造（数字・人物像・失敗結果・常識破壊・伏字・引きなど）を参考にして、固有数字とフックの言い回しは今回のテーマに合わせて新しく作ること。同じ表現・同じ構文を繰り返さない。")

    return "\n".join(lines)

THEMES = [
    # ── 集客 ──────────────────────────────────────
    "新規が来ない院の本当の原因",
    "予約が埋まらない院が変えるべき1つのこと",
    "紹介が自然に増える院の仕組み",
    "広告費ゼロで月10人新規を取る方法",
    "SNS集客できない院が発信でやっているズレ",
    "ホットペッパーを掲載しているのに新規が来ない院の特徴",
    "口コミが増えない院が無意識にやっていること",
    "集客が安定している院と不安定な院の決定的な差",
    "SNS投稿で新規患者が増える院と増えない院の違い",
    "初回来院者を次につなぐ院内の仕組み",
    "集客は頑張るものじゃなく整えるもの",
    "ホットペッパーのクーポン戦略で失敗する院の共通点",
    "Googleマップで上位表示されない院がやっていないこと",
    "LINE公式を活用して集客コストを下げた院の話",
    "予約が入らないとき真っ先に見直すべきもの",
    "新規集客より先にやるべきことがある",
    "患者さんの悩みを発信していない院が集客できない理由",

    # ── リピート・継続率・通院設計 ──────────────────────
    "リピートが取れない院が初回でやっていないこと",
    "3回以内に来なくなる患者さんの本当の理由",
    "次回予約を院内で取っていない院が毎月やらかしていること",
    "リピート率96%の院が初回でやっていること",
    "通院設計を伝えない院の継続率が低い理由",
    "患者さんが自然に通い続けたくなる院の特徴",
    "初回で通院プランを提示すると成約率が変わる理由",
    "3週間目と2ヶ月目に患者が離れる理由と対策",
    "問診の深さでリピート率が変わる理由",
    "患者さんに次回の理由を伝えていない院が失うもの",
    "カウンセリングを磨いたらリピート率が3倍になった院の話",
    "施術の説明より先に伝えるべきこと",
    "ゴール設定を初回にしていない院の継続率が低い理由",
    "患者さんが通院をやめたくなる時期は決まっている",
    "リピート率と継続率は違う。この差が経営を決める",

    # ── 単価・高単価・値上げ ───────────────────────────
    "値上げしたのに患者が増えた院がやった1つのこと",
    "高単価が売れない院の説明でやっている失敗",
    "初診単価5000円のまま5年経つ院が変えられない理由",
    "安売り競争から抜け出した院長が最初に変えたこと",
    "値上げで離れる患者より残る患者の方が大事な理由",
    "月商100万の院と月商300万の院の唯一の違い",
    "高単価提案で患者を警戒させない提案の順番",
    "値上げが怖い院長が価値を言葉にできていない理由",
    "低単価で患者を増やすほど利益が減る仕組み",
    "施術時間を減らしたら売上が上がった院の話",
    "メニューを3つに絞ったら成約率が上がった院の話",
    "患者が高単価を投資と感じる瞬間はいつか",
    "20分施術で満足度95%の院と60分施術で40%の院の差",
    "高単価を勧誘ではなく提案として伝える方法",
    "施術の説明をやめたら成約率が3倍になった院の話",

    # ── 月商・売上構造 ──────────────────────────────
    "月商100万で止まる院が時間を使っている場所",
    "月商300万を週休3日で実現する院の時間設計",
    "新規を増やしても利益が増えない院の構造",
    "売上より利益を先に考えている院長が安定している理由",
    "月商300万と月商100万、違いは初回設計だけ",
    "高単価×少患者数が月商300万への最短ルート",
    "売上が不安定な院に共通している思い込み",
    "月商が増えるのに手残りが減る院の構造",
    "稼働率100%を目指す院ほど月商300万に届かない理由",
    "月商100万円は呼吸していれば達成できる。次の壁の話",

    # ── 利益・経費・時間 ──────────────────────────────
    "営業時間を減らしたら売上が上がった院の話",
    "固定費が月商の50%を超えると経営が詰まる理由",
    "人件費率25%を超えたとき最初にすべき判断",
    "忙しいのに売上が上がらない院が時間を使っている場所",
    "週6営業をやめたら利益率が上がった院の話",
    "手残りを増やすために真っ先に見直すべき数字",
    "3000円×30人と12000円×8人、同じ月商で何が違うか",
    "忙しさは成功の証じゃない",
    "経営が苦しいとき感情で動く院長が悪化させるパターン",

    # ── 廃業・失敗事例 ───────────────────────────────
    "月商150万でスタッフを雇った院が3ヶ月で閉院した話",
    "60分3000円の院が半年で廃業した話",
    "値下げで患者を集め続けた院の末路",
    "低単価のまま3年続けた院長が廃業した理由",
    "急激な値上げで患者が消えて廃業した院の失敗",
    "廃業した院長に共通していた経営の思い込み",
    "開業3年で廃業する院と生き残る院の唯一の差",
    "スタッフを早く雇った院が詰まるパターン",
    "集客だけを頑張り続けて廃業した院の話",

    # ── 経営マインド・家族・時間 ─────────────────────────
    "週休3日にしてから売上が上がった理由",
    "経営は気合じゃなく設計の積み重ね",
    "頑張っているのに楽にならない院長が変えるべきこと",
    "夫婦経営で月商500万を達成した設計の話",
    "本音を話せる経営者仲間がいる院長と孤独な院長の差",
    "技術を磨くより先にやるべきことがある",
]

# ════════════════════════════════════════════════════════════
# AI×店舗経営テーマ（新コンセプトの主軸）
#   全テーマ「整体・整骨院・サロン経営者がAIを使った結果どう変わったか」の軸で統一。
#   汎用AIノウハウ（ChatGPT使い方◎選 等）は入れない。必ず店舗経営の結果に紐づける。
#   1日の投稿に占めるAI比率は generate_day.py の AI_RATIO で調整する。
# ════════════════════════════════════════════════════════════
AI_THEMES = [
    "パソコン苦手な46歳がAIで月商300万を維持できている理由",
    "事務スタッフを雇わずAIで月の事務作業を5時間に減らした院長の話",
    "AIで予約管理を自動化して人件費を月15万円削減した整骨院の話",
    "問診票をAIで作り直したら初回リピート率が85%になった話",
    "毎日のSNS投稿をAIで作って集客に時間を回せるようになった院長の話",
    "AIを使わないまま5年経つと何が起きるか同世代の院長に話します",
    "46歳でAIを始めた院長が3ヶ月後にやめた仕事5つ",
    "AIで月40時間の事務作業を削減した整体院がやったこと",
]

CTA_VARIANTS = [
    # 時間軸
    "パソコン苦手な僕でも週40時間削減できた話、気になる院長はプロフのLINEへ",
    "時間を売上に変えた仕組みを知りたい院長は、プロフのLINEを登録してください",
    # 売上・月商軸
    "月商100万から300万に変えた設計を話しています。気になる方はプロフのLINEへ",
    "AIが苦手な46歳が月商300万を10年維持できた理由、LINEで話しています",
    # 集客軸
    "広告費ゼロで新規が増えた仕組みを知りたい院長は、プロフのLINEを登録してください",
    "集客に疲れた院長に届けたい話があります。プロフのLINEへどうぞ",
    # リピート軸
    "リピート率96%の初回設計を知りたい院長は、プロフのLINEへ",
    "患者さんが自然に通い続ける院の仕組み、LINEで話しています",
    # 全部乗せ型
    "集客・リピート・売上・時間、全部変わった話。気になる院長はプロフのLINEへ",
    "AIが苦手な僕が月商300万・週休3日を手に入れた話、LINE登録しておいてください",
]

PROMPT_TREE = """
あなたは「ヒロ先生」。整体院・整骨院・サロンを営む46歳のアラフィフ院長です。
月商300万を10年以上維持しながら、同じ経営者に伴走しています。
Threadsで毎日発信し、院長の経営課題（集客・リピート・単価・利益）に答えるスタンス。

テーマ：「{theme}」

以下のフォーマットでThreadsのツリー投稿を3つ作成してください。

【1投稿目】フック1行のみ。5〜15文字が理想（最大20文字）。改行なし。
「…」や「があって…」で切り、続きを読みたくなる余白を作ること。
説明しない。タイトルにしない。感情か、数字か、余韻で引く。

必ず以下の8タイプのいずれかで書く。

タイプ①【超短感情型】感情の一言で引く（3〜12文字）
例：「ぶっちゃけ…」「許せません…」「悔しいです…」「マジで気づいてください」「衝撃です」「だから廃業したんです…」

タイプ②【数字+衝撃結果型】人物+数字+結末（最大25文字）「...」で切る
例：「月商150万でスタッフ雇った先生 半年で閉院しました...」「60分3000円の院が半年後に廃業しました…」

タイプ③【常識破壊断言型】思い込みを1文でひっくり返す（15文字以内）
例：「技術が上がっても売上は上がらない」「忙しさは成功の証じゃない」「高い単価が患者さんのためになる」

タイプ④【秘密・禁断知識型】「…があって」「なんですが」で引く（15文字以内）
例：「あまり知られてないのですが…」「悪用厳禁なんですが…」「実は教えたくないんですが…」

タイプ⑤【驚き指摘型】「え、まだ〜してるんですか？」（20文字以内）
例：「え、まだ施術に60分かけてるんですか？」「え、値下げで集客しようとしてますか？」

タイプ⑥【告白型】院長の感情・体験を打ち明ける（15文字以内）
例：「ごめんなさい…」「正直に言います」「だから休めないんですよ…」「これ言っていいのか…」

タイプ⑦【確認誘導型】「知ってますか？」「実は〜」（10文字以内）
例：「知ってますか？」「実は…」「まさか知らない…」

タイプ⑧【廃業警告型】廃業・末路をズバッと（15文字以内）
例：「これ知らないと一生売れません」「低単価は廃業への最短ルートです」「だから詰むんですよ…」

【重要】1投稿目はフックで終わること。説明は2投稿目以降でする。

【フック絶対禁止パターン】
❌ 説明的な長文（「〜する方法3つ」「〜の理由とは」など）
❌ 「〜という現実」「〜の共通点」「〜の構造」「〜の特徴」「〜について」で終わる
❌ タイトルっぽい体裁（「〜の違い」「〜を解説」など）

【2投稿目】種明かし・本文。80〜120文字。改行を使い読みやすくする。
以下のパターンを使うこと：
- A院 vs B院 対比（具体的な数字を入れる）例：「A院は月商150万で採用→閉院。B院は300万になってから採用→安定経営」
- または：問題の本質を数字で説明（%・万円・ヶ月・人）
- または：「順番がある」型（設計の説明）

【3投稿目】結論と締め。30〜50文字。{cta_line}

【絶対ルール】
- 「。」は使わない
- ハッシュタグは使わない
- 「→」は使わず改行か「・」を使う
- ダブルクォートは一切使わない
- です・ます調を徹底する
- 高圧的にならず伴走・応援スタンスで書く
- ツリー全体で150〜220文字（CTAあり時は最大240文字まで許容）
- テーマがAI・自動化に関する場合：46歳・パソコン苦手・アラフィフの親近感を出す。技術説明不要・結果の変化だけを語る

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
あなたは「ヒロ先生」。整体院・整骨院・サロンを営む46歳のアラフィフ院長です。
パソコンが苦手だった自分が、AIを使って月商300万を達成・維持できるようになり、
今は同じ整体・整骨院・サロンの経営者に、経営とAIの両面から伴走しながらThreadsで毎日発信しています。

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


def generate_thread(theme: str = None, cta: bool = False, list_style: bool = False, used_catches: list = None) -> list[str]:
    """ツリー投稿3件を生成してリストで返す"""
    if not theme:
        theme = random.choice(THEMES)

    if cta:
        cta_line = f"最後に自然な流れで次のCTAを1行添える：「{random.choice(CTA_VARIANTS)}」"
    else:
        cta_line = ""

    list_style_instruction = "\n【重要】1投稿目は必ず「〇〇 X選」形式（数字＋選）で始めること。例：「集客が変わる3つの習慣」「潰れる院の共通点5選」" if list_style else ""

    pattern_hint = _load_top_patterns()
    pattern_section = f"\n\n{pattern_hint}" if pattern_hint else ""

    avoid_section = ""
    if used_catches:
        recent = used_catches[-6:]
        avoid_lines = ["\n【使用済み・類似を避けること】以下の1投稿目は直近に使用済みです。全く同じ表現の繰り返しのみ避けること："]
        for c in recent:
            avoid_lines.append(f"・{c}")
        avoid_section = "\n".join(avoid_lines)

    prompt = PROMPT_TREE.format(theme=theme, cta_line=cta_line) + list_style_instruction + pattern_section + avoid_section

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


def generate_single_post(theme: str = None, used_catches: list = None) -> list[str]:
    """単体投稿1件を生成してリスト（1要素）で返す"""
    if not theme:
        theme = random.choice(THEMES)

    avoid_section = ""
    if used_catches:
        recent = used_catches[-20:]
        avoid_lines = ["\n【使用済み・類似を避けること】以下の投稿と同じ内容・言い回しを繰り返さないこと："]
        for c in recent:
            avoid_lines.append(f"・{c}")
        avoid_section = "\n".join(avoid_lines)

    prompt = PROMPT_SINGLE.format(theme=theme) + avoid_section

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
