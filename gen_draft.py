# -*- coding: utf-8 -*-
import json
import random
from datetime import datetime
import os

PATTERNS = {
    "A1": {"name": "衝撃落差型", "category": "信頼を積む", "description": "新規向け｜実体験・実績の落差でインパクト"},
    "A2": {"name": "数字インパクト型", "category": "信頼を積む", "description": "新規向け｜数字を頭に置いて掴む"},
    "A3": {"name": "弱さ・本音の開示型", "category": "信頼を積む", "description": "既存向け｜原点ストーリー・誠実さ"},
    "A4": {"name": "投資額・遠回り開示型", "category": "信頼を積む", "description": "新規向け｜権威と誠実の両取り"},
    "B1": {"name": "会話・セリフ再現型", "category": "問題提起", "description": "既存向け｜実際の会話を再現"},
    "B2": {"name": "リスト／やめたこと型", "category": "問題提起", "description": "既存向け｜具体的な行動リスト"},
    "B3": {"name": "常識破壊×逆説型", "category": "問題提起", "description": "新規向け｜集客じゃなく売上の話へ転換"},
    "C1": {"name": "孤独共感型", "category": "思想・あり方", "description": "新規向け｜院長の孤独への共感"},
    "C2": {"name": "名言・本質突き型", "category": "思想・あり方", "description": "新規向け｜言い切り格言"},
    "C3": {"name": "宣言＋共感ベイト型", "category": "思想・あり方", "description": "既存向け｜フォローされる理由"}
}

STYLE_RULES = {
    "句読点": "。なし（体言止め着地）",
    "ハッシュタグ": "なし",
    "トーン": "言い切り中心",
    "命令形": "なし",
    "終わり": "体言止め（～です・～します）",
    "波ダッシュ": "使用OK（ただしハッシュタグ代わりにはしない）",
    "LINE_CTA": "4本に1本（25%）"
}

TIME_SCHEDULE = [
    "05:00", "05:15", "05:30", "05:45", "06:00", "06:15", "06:30", "06:45",
    "07:00", "07:15", "07:30", "07:45", "08:00", "08:15", "08:30", "08:45",
    "09:00", "09:15", "09:30", "09:45", "10:00", "10:15", "10:30", "10:45",
    "11:00", "11:15", "11:30", "11:45", "12:00", "12:15", "12:30", "12:45",
    "13:00", "13:15", "13:30", "13:45", "14:00", "14:15", "14:30", "14:45",
    "15:00", "15:15", "15:30", "15:45", "16:00", "16:15", "16:30", "16:45",
    "17:00", "17:15", "17:30", "17:45", "18:00", "18:15", "18:30", "18:45",
    "19:00", "19:15", "19:30", "19:45", "20:00", "20:15", "20:30", "20:45",
    "21:00", "21:15", "21:30", "21:45", "22:00"
]

PERSONA_RATIO = {"更年期": 0.70, "ブライダル": 0.30}

SAMPLE_CONTENT = {
    "A1": {
        "更年期": "月商300万の院が半年で150万まで落ちました。原因はスタッフ2名の離脱。でも値下げも広告増額もしてない。単価設計とLINE導線を組み直しただけ。今は250万、次は350万。落ちた時の正解は足し算じゃなく整理です",
        "ブライダル": "開業3年で廃業を考えた院長が、単価改定1つで月商が25万増えた話"
    },
    "B3": {
        "更年期": "集客に困ってるオーナーほど本当は集客に困ってません。困ってるのは売上のほう。客数を増やしても単価が低いままなら忙しいだけで残らない。だから新規より単価設計を先にやった。集客は入口、売上は設計です",
        "ブライダル": "ブライダルの相談が増えても、単価が安いままなら時間ばかり増えます。ウェディング層は質で選ぶから、1件の価値を上げることから始めましょう"
    },
    "C2": {
        "更年期": "「高い」の反対は「安い」じゃありません。「価値が伝わってない」です。値段で選ばれた人は値段で去ります。伝われば59,800円でも498,000円でも申し込みは来る。高いかどうかを決めるのは価格じゃなく伝え方です",
        "ブライダル": "ブライダル向けの高単価メニューは、技術より「あなたと一緒にいたい」という信頼で売れます。値段じゃなく関係性を磨いてください"
    }
}


def generate_posts(total=50, tree_ratio=0.7):
    random.seed(42)
    posts = []
    pattern_list = list(PATTERNS.keys())
    pattern_idx = 0
    for i in range(total):
        post_num = i + 1
        time_slot = TIME_SCHEDULE[i % len(TIME_SCHEDULE)]
        post_type = "tree" if random.random() < tree_ratio else "standalone"
        pattern = pattern_list[pattern_idx % len(pattern_list)]
        pattern_idx += 1
        persona = "更年期" if random.random() < PERSONA_RATIO["更年期"] else "ブライダル"
        has_cta = (i % 4 == 3)
        content_sample = SAMPLE_CONTENT.get(pattern, {}).get(
            persona, f"[{pattern}_{persona}のコンテンツ] パターン定義に従い生成"
        )
        post_data = {
            "id": post_num,
            "time": time_slot,
            "type": post_type,
            "pattern": pattern,
            "persona": persona,
            "has_cta": has_cta,
            "content_sample": content_sample,
            "status": "draft"
        }
        posts.append(post_data)
    return posts


posts = generate_posts(total=50, tree_ratio=0.7)
tree_count = sum(1 for p in posts if p["type"] == "tree")
standalone_count = sum(1 for p in posts if p["type"] == "standalone")
cta_count = sum(1 for p in posts if p["has_cta"])

json_output = {
    "schedule_date": datetime.now().strftime("%Y-%m-%d"),
    "total_posts": len(posts),
    "tree_count": tree_count,
    "standalone_count": standalone_count,
    "cta_count": cta_count,
    "patterns": PATTERNS,
    "style_rules": STYLE_RULES,
    "posts": posts
}

out_dir = r"C:\Users\tujid\OneDrive\Desktop\コンサル投稿確認"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "threads_50_draft.json")

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(json_output, f, ensure_ascii=False, indent=2)

print("JSON生成完了")
print(f"統計: 全{len(posts)}本 | ツリー{tree_count}本 | 単体{standalone_count}本 | CTA{cta_count}本")
print(f"出力: {out_path}")
