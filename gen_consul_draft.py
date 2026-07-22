# -*- coding: utf-8 -*-
import json
import random
from datetime import datetime
import os

PATTERNS = {
    "A1": {"name": "衝撃落差型", "category": "信頼を積む", "personas": ["一人院", "小規模チーム", "成長期"], "issues": ["月商落下", "組織化の壁"]},
    "A2": {"name": "数字インパクト型", "category": "信頼を積む", "personas": ["成長期", "小規模チーム"], "issues": ["単価設計", "月商"]},
    "A3": {"name": "弱さ・本音の開示型", "category": "信頼を積む", "personas": ["一人院", "新規独立"], "issues": ["時間確保", "孤独"]},
    "A4": {"name": "投資額・遠回り開示型", "category": "信頼を積む", "personas": ["成長期", "小規模チーム"], "issues": ["投資判断", "経営学習"]},
    "B1": {"name": "会話・セリフ再現型", "category": "問題提起", "personas": ["小規模チーム", "成長期"], "issues": ["新規集客", "スタッフ育成"]},
    "B2": {"name": "リスト／やめたこと型", "category": "問題提起", "personas": ["一人院", "小規模チーム"], "issues": ["単価設計", "時間確保", "新規集客"]},
    "B3": {"name": "常識破壊×逆説型", "category": "問題提起", "personas": ["一人院", "成長期"], "issues": ["単価設計", "新規集客"]},
    "C1": {"name": "孤独共感型", "category": "思想・あり方", "personas": ["一人院", "新規独立"], "issues": ["孤独", "時間確保", "相談相手"]},
    "C2": {"name": "名言・本質突き型", "category": "思想・あり方", "personas": ["一人院", "小規模チーム", "成長期"], "issues": ["経営観", "価値観"]},
    "C3": {"name": "宣言＋共感ベイト型", "category": "思想・あり方", "personas": ["成長期"], "issues": ["コミュニティ", "信頼構築"]}
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
    "05:00","05:15","05:30","05:45","06:00","06:15","06:30","06:45",
    "07:00","07:15","07:30","07:45","08:00","08:15","08:30","08:45",
    "09:00","09:15","09:30","09:45","10:00","10:15","10:30","10:45",
    "11:00","11:15","11:30","11:45","12:00","12:15","12:30","12:45",
    "13:00","13:15","13:30","13:45","14:00","14:15","14:30","14:45",
    "15:00","15:15","15:30","15:45","16:00","16:15","16:30","16:45",
    "17:00","17:15","17:30","17:45","18:00","18:15","18:30","18:45",
    "19:00","19:15","19:30","19:45","20:00","20:15","20:30","20:45",
    "21:00","21:15","21:30","21:45","22:00"
]

SAMPLE_CONTENT = {
    "A1": {
        "一人院": "月商150万の院が集客に悩んでいた。原因はスタッフいないのに広告ばかり。単価を30%上げて、LINE導線を整えたら新規は減ったが利益は増えた",
        "小規模チーム": "月商300万で月30万の赤字。スタッフ2名なのに施術比率が低かった。院長の施術時間を守った結果、6ヶ月で黒字化",
        "成長期": "月商500万を超えた院長が必ずぶつかる壁がある。それは『システム化の無視』。成長した院ほど、人頼みから仕組み頼みへの転換が遅れている"
    },
    "B3": {
        "一人院": "集客に困ってるオーナーほど本当は集客に困ってません。困ってるのは単価。客数を増やしても単価が低いままなら忙しいだけで残らない",
        "成長期": "新規客を増やすことに必死な院長ほど、既存客の単価を見ていない。新規より既存。集客より単価設計が経営の基本です"
    },
    "C1": {
        "一人院": "一人で院をやってると相談できる人がいない。明日の予約、今月の売上、値下げすべきか。隣の同業には弱みを見せられない。その孤独は痛いほどわかります",
        "新規独立": "開業前の不安、開業後の孤独。誰に相談していいのか分からない院長は多い。だから相談できる場を作りました"
    },
    "C2": {
        "一人院": "『高い』の反対は『安い』じゃありません。『価値が伝わってない』です。値段で選ばれた人は値段で去る。伝われば高くても申し込みは来る",
        "成長期": "月商が増えるほど『何のためにやっているのか』を忘れる院長がいます。利益より、患者さんへの想いを思い出してください"
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
        pattern_info = PATTERNS[pattern]
        pattern_idx += 1
        persona = random.choice(pattern_info["personas"])
        issue = random.choice(pattern_info["issues"])
        has_cta = (i % 4 == 3)
        if pattern in SAMPLE_CONTENT and persona in SAMPLE_CONTENT[pattern]:
            content_sample = SAMPLE_CONTENT[pattern][persona]
        else:
            content_sample = f"[{pattern} | {persona} | {issue}] 院長向けコンテンツ"
        post_data = {
            "id": post_num,
            "time": time_slot,
            "type": post_type,
            "pattern": pattern,
            "persona": persona,
            "issue": issue,
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
persona_breakdown = {
    "一人院": sum(1 for p in posts if p["persona"] == "一人院"),
    "小規模チーム": sum(1 for p in posts if p["persona"] == "小規模チーム"),
    "成長期": sum(1 for p in posts if p["persona"] == "成長期"),
    "新規独立": sum(1 for p in posts if p["persona"] == "新規独立"),
}

json_output = {
    "schedule_date": datetime.now().strftime("%Y-%m-%d"),
    "total_posts": len(posts),
    "tree_count": tree_count,
    "standalone_count": standalone_count,
    "cta_count": cta_count,
    "persona_breakdown": persona_breakdown,
    "patterns": PATTERNS,
    "style_rules": STYLE_RULES,
    "posts": posts
}

out_dir = r"C:\Users\tujid\OneDrive\Desktop\コンサル投稿確認"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "threads_50_consul_draft.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(json_output, f, ensure_ascii=False, indent=2)

print("JSON生成完了")
print(f"統計: 全{len(posts)}本 | ツリー{tree_count}本 | 単体{standalone_count}本 | CTA{cta_count}本")
print("ペルソナ別:")
for persona, count in persona_breakdown.items():
    print(f"  {persona}: {count}本")
print(f"出力: {out_path}")
