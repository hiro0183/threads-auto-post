"""
投稿テキストを丁寧口調に変換するポストプロセッサ
- 〇〇ない → 〇〇ません（行末・文末）
- ないです → ません
- 客 → お客様
- こない → 来ません
"""

import json
import re
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "posts"

# 変換しない例外語（複合語）
EXCEPTIONS = {"観客", "客室", "客員", "客体", "客席", "客観", "顧客", "集客", "来客", "送客", "迎客", "招客"}

def make_polite(text: str) -> str:
    # ──── 生成時のモデルミス修正 ────
    # じゃません → ではありません
    text = text.replace("じゃません", "ではありません")
    # 二重変換ミス：おお客様様 → お客様
    text = re.sub(r"おお+客様+", "お客様", text)
    # 複合語誤変換修正：集お客様 → 集客 など
    text = text.replace("集お客様", "集客")
    text = text.replace("顧お客様", "顧客")
    text = text.replace("来お客様", "来客")

    # ──── 敬語変換 ────
    # ないです → ません
    text = text.replace("ないですね", "ませんね")
    text = text.replace("ないです", "ません")

    # じゃない → ではありません（行末・文末）
    text = re.sub(r"じゃない(。|\n|$)", lambda m: "ではありません" + m.group(1), text, flags=re.MULTILINE)
    # ではない → ではありません（行末・文末）
    text = re.sub(r"ではない(。|\n|$)", lambda m: "ではありません" + m.group(1), text, flags=re.MULTILINE)

    # 行末・文末の「ない」→「ません」
    text = re.sub(r"ない(。|\n|$)", lambda m: "ません" + m.group(1), text, flags=re.MULTILINE)

    # こない → 来ません（行中含む）
    text = re.sub(r"こない(?=[\s\n。、]|$)", "来ません", text, flags=re.MULTILINE)

    # 「客」→「お客様」（お客様・観客等の複合語は除外）
    def replace_kyaku(m):
        start = m.start()
        end = m.end()
        before = text[max(0, start-1):start]
        after = text[end:end+1]
        compound = before + "客" + after
        # 既にお客様、または複合語
        for exc in EXCEPTIONS:
            if exc in compound:
                return "客"
        if before == "お" and after == "様":
            return "客"  # お客様のまま
        if before == "お":
            return "客"  # お客 → そのまま（後でお客様に）
        return "お客様"

    text = re.sub(r"客", replace_kyaku, text)
    # お客 → お客様（まだ様がついてないケース）
    text = re.sub(r"お客(?!様)", "お客様", text)

    return text


def process_file(date_str: str) -> int:
    path = POSTS_DIR / f"{date_str}.json"
    if not path.exists():
        print(f"  ファイルなし: {date_str}")
        return 0

    data = json.loads(path.read_text(encoding="utf-8"))
    new_data = {}
    changed = 0

    for slot, posts in data.items():
        new_posts = []
        for p in posts:
            new_p = make_polite(p)
            if new_p != p:
                changed += 1
            new_posts.append(new_p)
        new_data[slot] = new_posts

    path.write_text(json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return changed


if __name__ == "__main__":
    import sys
    dates = sys.argv[1:] if len(sys.argv) > 1 else ["2026-06-30", "2026-07-01", "2026-07-02"]

    for d in dates:
        n = process_file(d)
        print(f"{d}: {n}箇所を丁寧語に変換")
