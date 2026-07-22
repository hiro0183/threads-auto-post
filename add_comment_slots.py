"""
5/15〜5/31のJSONファイルに5つのコメント誘導スロットを追加するスクリプト
スロット: 08:15 / 11:15 / 14:15 / 17:15 / 22:30
"""
import json
from pathlib import Path
from datetime import date, timedelta

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"

# スロットごとに3バリエーション作成して日ごとにローテーション
COMMENT_VARIANTS = {
    "08:15": [
        "今の施術1回あたりの客単価、コメントで教えてください\n数字だけで大丈夫です\n同じ境遇の院長さんの参考になると思います",
        "月に何人の新規患者さんを集客できていますか\n数字だけでも教えてもらえると嬉しいです",
        "院を開業して何年になりますか\nコメントで教えてもらえると嬉しいです",
    ],
    "11:15": [
        "初回来院の患者さん、また来ていますか\n「リピートできてる/できてない」どちらか、コメントで教えてもらえると嬉しいです",
        "患者さんへのリピート促進、意識的にやっていますか\n「してる/してない」コメントで教えてもらえると嬉しいです",
        "次回予約の案内、施術後に毎回できていますか\n「できてる/できてない」コメントで教えてもらえると嬉しいです",
    ],
    "14:15": [
        "今の経営の一番の悩み、「集客」と「リピート」どちらですか\nコメントで教えてもらえると嬉しいです",
        "売上が安定しないとき、一番の原因は何だと思いますか\n「新規不足/リピート不足/単価不足」コメントで教えてもらえると嬉しいです",
        "一番時間を取られている業務は何ですか\n「施術/SNS/事務作業/集客」から選んでコメントで教えてもらえると嬉しいです",
    ],
    "17:15": [
        "SNSを週に何日更新していますか\n「毎日/週3/週1/ほぼしてない」コメントで教えてもらえると嬉しいです",
        "Googleマップの口コミ、今いくつありますか\n数字だけでも教えてもらえると嬉しいです",
        "今の月商に満足していますか\n「満足/まあまあ/不満」コメントで教えてもらえると嬉しいです",
    ],
    "22:30": [
        "1人で経営していて、一番しんどかった瞬間を一言で教えてください",
        "今日の施術、何人でしたか\n数字だけで大丈夫です",
        "明日やろうと思っているけど後回しにしていること、一言で教えてください",
    ],
}

# バリエーションのオフセット（スロットごとにずらして同じ日でも内容が被らないように）
SLOT_OFFSETS = {
    "08:15": 0,
    "11:15": 1,
    "14:15": 2,
    "17:15": 0,
    "22:30": 1,
}

start_date = date(2026, 5, 15)
end_date = date(2026, 5, 31)

added = 0
skipped = 0

current = start_date
day_index = 0
while current <= end_date:
    json_file = POSTS_DIR / f"{current}.json"
    if not json_file.exists():
        print(f"[SKIP] {current}: ファイルなし")
        current += timedelta(days=1)
        day_index += 1
        continue

    data = json.loads(json_file.read_text(encoding="utf-8"))
    updated = False

    for slot, variants in COMMENT_VARIANTS.items():
        if slot in data:
            print(f"[SKIP] {current} {slot}: 既に存在")
            skipped += 1
            continue
        offset = SLOT_OFFSETS[slot]
        variant_index = (day_index + offset) % len(variants)
        data[slot] = [variants[variant_index]]
        added += 1
        updated = True

    if updated:
        json_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[OK] {current}: 5スロット追加")

    current += timedelta(days=1)
    day_index += 1

print(f"\n完了: {added}件追加 / {skipped}件スキップ")
