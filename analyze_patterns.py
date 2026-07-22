"""
インサイトデータから伸びた投稿のパターンを分析してObsidianに保存するスクリプト

使い方:
  python analyze_patterns.py        # 最新データで分析・保存
  python analyze_patterns.py --top 20  # 上位20件で分析（デフォルト15件）
"""

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
INSIGHTS_DATA_FILE = BASE_DIR / "insights_data.jsonl"
OBSIDIAN_PATTERN_DIR = Path(r"C:\Users\tujid\OneDrive\Desktop\HIRAYASU\コンサルThreads\投稿パターン")

JST = timezone(timedelta(hours=9))


def classify_catch(catch: str) -> str:
    """1投稿目のキャッチを型に分類"""
    import re
    if re.search(r"\d+選|[２-９一二三四五六七八九十]+選", catch):
        return "〇選型"
    if re.search(r"怖|ヤバ|詰ま|廃業|赤字|損|危|無理|できない|取れない|増えない|出ない", catch):
        return "ネガティブ訴求型"
    if re.search(r"今月|たった|すぐ|1週間|即|変わった|増えた|取れた|伸びた", catch):
        return "短期快楽型"
    if re.search(r"へ$|ですか$|ませんか$|ないですか$|悩み|気持ち|怖く|辛い|孤独", catch):
        return "感情共感型"
    if re.search(r"理由|原因|共通点|違い|特徴|秘密|仕組み|方法|コツ|ポイント", catch):
        return "知的好奇心型"
    if re.search(r"AI|自動化|ChatGPT|Claude|メタ|Meta|広告", catch):
        return "AI・テック型"
    # 暗示型: 語尾を伏せて引きを作るタイプ（結末・詳細を明かさない）
    if re.search(r"…$|\.\.\.$|\.{3}$", catch):
        return "暗示型"
    # 断言型: 疑問系でも伏字でもなく言い切って終わるタイプ
    if re.search(r"(です|ます|でした|ました|ません)[。.]?$", catch) and not re.search(r"[?？]", catch):
        return "断言型"
    return "直球型"


def eng_rate(r: dict) -> float:
    """エンゲージメント率（%）を返す"""
    v = r.get("views", 0) or 0
    if v == 0:
        return 0.0
    eng = sum(r.get(m, 0) or 0 for m in ["likes", "replies", "reposts", "quotes"])
    return round(eng / v * 100, 2)


def load_insights() -> list:
    if not INSIGHTS_DATA_FILE.exists():
        return []
    rows = []
    seen_ids = set()
    for line in INSIGHTS_DATA_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            row = json.loads(line)
            rid = row.get("root_id", "")
            if rid and rid in seen_ids:
                continue  # 重複スキップ（--allで再集計された場合）
            seen_ids.add(rid)
            rows.append(row)
        except Exception:
            pass
    return rows


def build_markdown(rows: list, top_n: int) -> str:
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    valid = [r for r in rows if isinstance(r.get("views"), int) and (r.get("views") or 0) > 0]
    if not valid:
        return f"# 投稿パターン分析\n\n> 更新: {now_str}\n\nデータがまだありません\n"

    top_views = sorted(valid, key=lambda x: x["views"], reverse=True)[:top_n]
    top_eng_rate = sorted(valid, key=lambda x: eng_rate(x), reverse=True)[:top_n]

    # 型別集計
    type_counts: dict[str, list] = {}
    for r in valid:
        t = classify_catch(r.get("catch", ""))
        type_counts.setdefault(t, []).append(r)

    lines = [f"# 投稿パターン分析\n"]
    lines.append(f"> 更新: {now_str}　/ 分析対象: {len(valid)}件 / 上位表示: {top_n}件\n")

    # 型別サマリー
    lines.append("## 型別パフォーマンス\n")
    lines.append("| 型 | 件数 | 平均Views | 平均エンゲージ | 平均エンゲージ率 |")
    lines.append("|:---|---:|---:|---:|---:|")
    for t, rs in sorted(type_counts.items(), key=lambda x: -sum(r.get("views", 0) for r in x[1]) / len(x[1])):
        avg_views = int(sum(r.get("views", 0) for r in rs) / len(rs))
        avg_eng = int(sum(
            sum(r.get(m, 0) or 0 for m in ["likes", "replies", "reposts", "quotes"])
            for r in rs
        ) / len(rs))
        avg_er = round(sum(eng_rate(r) for r in rs) / len(rs), 2)
        lines.append(f"| {t} | {len(rs)} | {avg_views:,} | {avg_eng} | {avg_er}% |")

    # 時間帯別パフォーマンス
    lines.append("\n## 時間帯別パフォーマンス\n")
    hour_data: dict[str, list] = {}
    for r in valid:
        slot = r.get("slot", "")
        hour = slot.split(":")[0] if ":" in slot else "??"
        hour_data.setdefault(hour, []).append(r)
    lines.append("| 時間帯 | 件数 | 平均Views | 平均エンゲージ率 |")
    lines.append("|:---:|---:|---:|---:|")
    for hour in sorted(hour_data.keys()):
        rs = hour_data[hour]
        avg_v = int(sum(r.get("views", 0) for r in rs) / len(rs))
        avg_er = round(sum(eng_rate(r) for r in rs) / len(rs), 2)
        lines.append(f"| {hour}時台 | {len(rs)} | {avg_v:,} | {avg_er}% |")

    # 上位投稿一覧（Views順）
    lines.append(f"\n## 上位{top_n}投稿（Views順）\n")
    lines.append("| 日付 | 時刻 | 型 | Views | エンゲージ率 | キャッチ |")
    lines.append("|:---:|:---:|:---:|---:|---:|:---|")
    for r in top_views:
        er = eng_rate(r)
        t = classify_catch(r.get("catch", ""))
        catch = r.get("catch", "")[:28] + "…" if len(r.get("catch", "")) > 28 else r.get("catch", "")
        lines.append(f"| {r.get('date','')} | {r.get('slot','')} | {t} | {r.get('views',0):,} | {er}% | {catch} |")

    # こすり候補（エンゲージ率上位）
    lines.append(f"\n## こすり候補（エンゲージ率上位10件）\n")
    lines.append("> この投稿の構成・リズム・言葉選びを参考にリミックスする\n")
    lines.append("| 順位 | 日付 | Views | エンゲージ率 | 型 | キャッチ |")
    lines.append("|:---:|:---:|---:|---:|:---:|:---|")
    for i, r in enumerate(top_eng_rate[:10], 1):
        er = eng_rate(r)
        t = classify_catch(r.get("catch", ""))
        catch = r.get("catch", "")[:30] + "…" if len(r.get("catch", "")) > 30 else r.get("catch", "")
        lines.append(f"| {i} | {r.get('date','')} | {r.get('views',0):,} | {er}% | {t} | {catch} |")

    # こすり候補 全文（エンゲージ率上位5件）
    lines.append(f"\n## こすり候補 全文（エンゲージ率上位5件）\n")
    for i, r in enumerate(top_eng_rate[:5], 1):
        er = eng_rate(r)
        t = classify_catch(r.get("catch", ""))
        lines.append(f"### {i}位｜{r.get('date','')} {r.get('slot','')}｜{t}｜Views: {r.get('views',0):,}｜エンゲージ率: {er}%\n")
        for j, post in enumerate(r.get("posts", []), 1):
            label = f"{j}投稿目" if r.get("post_type") == "tree" else "本文"
            lines.append(f"**{label}:**")
            lines.append(post)
            lines.append("")

    # Views上位5件 全文
    lines.append(f"\n## Views上位5投稿 全文\n")
    for i, r in enumerate(top_views[:5], 1):
        er = eng_rate(r)
        t = classify_catch(r.get("catch", ""))
        lines.append(f"### {i}位｜{r.get('date','')} {r.get('slot','')}｜{t}｜Views: {r.get('views',0):,}｜エンゲージ率: {er}%\n")
        for j, post in enumerate(r.get("posts", []), 1):
            label = f"{j}投稿目" if r.get("post_type") == "tree" else "本文"
            lines.append(f"**{label}:**")
            lines.append(post)
            lines.append("")

    # 生成ヒント
    top_types = sorted(type_counts.items(), key=lambda x: -sum(r.get("views", 0) for r in x[1]) / len(x[1]))
    best_type = top_types[0][0] if top_types else "不明"
    best_er_type = sorted(type_counts.items(), key=lambda x: -sum(eng_rate(r) for r in x[1]) / len(x[1]))[0][0] if type_counts else "不明"

    lines.append("## 生成ヒント（自動更新）\n")
    lines.append(f"- Views最大型: **{best_type}**")
    lines.append(f"- エンゲージ率最大型: **{best_er_type}**")
    lines.append(f"- Views上位10件のキャッチ:")
    for r in top_views[:10]:
        lines.append(f"  - {r.get('catch', '')}")

    return "\n".join(lines)


def main():
    top_n = 15
    if "--top" in sys.argv:
        idx = sys.argv.index("--top")
        if idx + 1 < len(sys.argv):
            top_n = int(sys.argv[idx + 1])

    rows = load_insights()
    if not rows:
        print("インサイトデータがありません。先に collect_insights.py を実行してください")
        return

    print(f"分析対象: {len(rows)}件")

    OBSIDIAN_PATTERN_DIR.mkdir(parents=True, exist_ok=True)
    md_file = OBSIDIAN_PATTERN_DIR / "高エンゲージ投稿パターン.md"
    md_file.write_text(build_markdown(rows, top_n), encoding="utf-8")
    print(f"保存: {md_file}")


if __name__ == "__main__":
    main()
