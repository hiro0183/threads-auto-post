"""
週次レポート生成スクリプト（AIを使わない純粋集計。文章生成・解釈はしない）

毎週月曜朝に自動実行し、Fable5週次セッションの入力になる1枚のMarkdownを生成する。
`analyze_patterns.py` の classify_catch、`generate_dashboard.py` の classify_theme を流用。

出力: コンサルThreads\\インサイト\\週次レポート\\YYYY-Www.md

使い方:
  python weekly_report.py
"""

import json
import re
import statistics
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict, Counter

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from analyze_patterns import classify_catch, eng_rate  # noqa: E402
from generate_dashboard import classify_theme  # noqa: E402

def _data_file(name: str) -> Path:
    """データファイルの場所を返す。ローカル(フル)を優先し、無ければ累積sync/を読む。

    ローカルPC: BASE_DIR/{name}（pull_insightsが蓄積したフル履歴）
    クラウド週次ルーティン: BASE_DIR/{name}は無いので sync/{name}（github_syncの累積）を使う
    """
    primary = BASE_DIR / name
    if primary.exists():
        return primary
    fallback = BASE_DIR / "sync" / name
    return fallback if fallback.exists() else primary


INSIGHTS_DATA_FILE = _data_file("insights_data.jsonl")
POST_LOG_FILE = _data_file("post_log.jsonl")
FOLLOWER_LOG_FILE = _data_file("follower_log.jsonl")
OBSIDIAN_REPORT_DIR = Path(r"C:\Users\tujid\OneDrive\Desktop\HIRAYASU\コンサルThreads\インサイト\週次レポート")
LINE_MANUAL_FILE = OBSIDIAN_REPORT_DIR / "_LINE流入_手動記入.jsonl"

JST = timezone(timedelta(hours=9))

# 2026-06-29導入のCTA10種（content_generator.py CTA_VARIANTSと対応。文言の一部一致で判定）
CTA_TYPES = [
    ("時間軸", ["週40時間削減できた話", "時間を売上に変えた仕組み"]),
    ("売上・月商軸", ["月商100万から300万に変えた設計", "月商300万を10年維持できた理由"]),
    ("集客軸", ["広告費ゼロで新規が増えた仕組み", "集客に疲れた院長に届けたい話"]),
    ("リピート軸", ["リピート率96%の初回設計", "患者さんが自然に通い続ける院の仕組み"]),
    ("全部乗せ型", ["集客・リピート・売上・時間、全部変わった話", "月商300万・週休3日を手に入れた話"]),
]


def count_posted_total() -> int:
    """post_log.jsonlの投稿数（重複root_id除去）"""
    if not POST_LOG_FILE.exists():
        return 0
    ids = set()
    for line in POST_LOG_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        post_ids = d.get("post_ids") or []
        if post_ids:
            ids.add(post_ids[0])
    return len(ids)


def load_insights() -> list:
    """重複除去した全insightsデータ（views>0のみ）"""
    if not INSIGHTS_DATA_FILE.exists():
        return []
    rows = []
    seen_ids = set()
    for line in INSIGHTS_DATA_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        rid = row.get("root_id", "")
        if rid and rid in seen_ids:
            continue
        seen_ids.add(rid)
        if isinstance(row.get("views"), int) and (row.get("views") or 0) > 0:
            rows.append(row)
    return rows


def cta_type_of(row: dict):
    """postsの最終投稿文からCTA種別を判定。マッチしなければNone"""
    if not row.get("posts"):
        return None
    last_post = row["posts"][-1]
    for label, needles in CTA_TYPES:
        for needle in needles:
            if needle in last_post:
                return label
    return None


def ending_of(catch: str) -> str:
    """語尾の鮮度トラッキング用キー。末尾の記号を落として末尾4文字を語尾として扱う"""
    c = (catch or "").rstrip("　 \n")
    c = re.sub(r"[！!?？…。.]+$", "", c)
    if not c:
        return "(空)"
    return c[-4:] if len(c) >= 4 else c


def week_bounds(offset_weeks: int, today=None):
    """offset_weeks=1 → 先週(月〜日)の(開始日, 終了日)をdateで返す"""
    today = today or datetime.now(JST).date()
    this_monday = today - timedelta(days=today.weekday())
    start = this_monday - timedelta(weeks=offset_weeks)
    end = start + timedelta(days=6)
    return start, end


def filter_week(rows: list, start, end) -> list:
    s, e = start.isoformat(), end.isoformat()
    return [r for r in rows if s <= r.get("date", "") <= e]


def median(values):
    return int(statistics.median(values)) if values else 0


def build_slot_table(rows: list) -> list:
    by_slot = defaultdict(list)
    for r in rows:
        by_slot[r.get("slot", "??")].append(r.get("views", 0))
    result = []
    for slot, vs in sorted(by_slot.items()):
        result.append({
            "slot": slot, "n": len(vs), "median": median(vs),
            "avg": int(sum(vs) / len(vs)), "max": max(vs),
            "flag": median(vs) < 100,
        })
    return result


def build_type_table(rows: list) -> list:
    by_type = defaultdict(list)
    for r in rows:
        by_type[classify_catch(r.get("catch", ""))].append(r)
    result = []
    for t, rs in by_type.items():
        vs = [r.get("views", 0) for r in rs]
        result.append({
            "type": t, "n": len(rs), "avg": int(sum(vs) / len(vs)),
            "median": median(vs),
            "avg_er": round(sum(eng_rate(r) for r in rs) / len(rs), 2),
        })
    return sorted(result, key=lambda x: -x["avg"])


def build_theme_table(rows: list) -> list:
    by_theme = defaultdict(list)
    for r in rows:
        by_theme[classify_theme(r.get("catch", ""))].append(r)
    result = []
    for theme, rs in by_theme.items():
        vs = [r.get("views", 0) for r in rs]
        result.append({
            "theme": theme, "n": len(rs), "avg": int(sum(vs) / len(vs)),
        })
    return sorted(result, key=lambda x: -x["avg"])


def build_tree_length_table(rows: list) -> list:
    by_len = defaultdict(list)
    for r in rows:
        n_posts = len(r.get("posts") or [])
        if r.get("post_type") != "tree":
            key = "単体"
        elif n_posts <= 2:
            key = "2投稿ツリー"
        else:
            key = "3投稿以上ツリー"
        by_len[key].append(r.get("views", 0))
    result = []
    for key, vs in by_len.items():
        result.append({"label": key, "n": len(vs), "avg": int(sum(vs) / len(vs)) if vs else 0})
    return result


def build_cta_table(rows: list) -> list:
    by_cta = defaultdict(list)
    for r in rows:
        cta = cta_type_of(r)
        if cta:
            by_cta[cta].append(r)
    result = []
    for cta, rs in by_cta.items():
        vs = [r.get("views", 0) for r in rs]
        replies = [r.get("replies", 0) or 0 for r in rs]
        result.append({
            "cta": cta, "n": len(rs), "avg_views": int(sum(vs) / len(vs)),
            "avg_replies": round(sum(replies) / len(replies), 1),
        })
    return sorted(result, key=lambda x: -x["avg_views"])


def load_line_manual() -> dict:
    """週ごとのLINE流入手動記入（週開始日=key）"""
    if not LINE_MANUAL_FILE.exists():
        return {}
    result = {}
    for line in LINE_MANUAL_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            d = json.loads(line)
            result[d["week_start"]] = d
        except Exception:
            pass
    return result


def ensure_line_manual_entry(week_start: str):
    """当週の記入欄がなければ空エントリを追記（人間が後で埋める）"""
    entries = load_line_manual()
    if week_start in entries:
        return
    OBSIDIAN_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(LINE_MANUAL_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "week_start": week_start,
            "line_additions": None,
            "note": "エルメ管理画面の友だち追加数を手動で記入してください",
        }, ensure_ascii=False) + "\n")


def freshness_check(rows_14d: list, all_rows: list) -> list:
    """直近14日で5回超使われた型・語尾のうち、直近成績が全期間平均を下回るものに飽き警告"""
    warnings = []

    # 型の鮮度
    all_by_type = defaultdict(list)
    for r in all_rows:
        all_by_type[classify_catch(r.get("catch", ""))].append(r.get("views", 0))
    recent_by_type = defaultdict(list)
    for r in rows_14d:
        recent_by_type[classify_catch(r.get("catch", ""))].append(r.get("views", 0))
    for t, vs in recent_by_type.items():
        if len(vs) > 5:
            recent_avg = sum(vs) / len(vs)
            overall_avg = sum(all_by_type[t]) / len(all_by_type[t]) if all_by_type[t] else 0
            if overall_avg > 0 and recent_avg < overall_avg * 0.7:
                warnings.append(f"型「{t}」: 直近14日{len(vs)}回使用・平均{int(recent_avg):,}v（全期間平均{int(overall_avg):,}vの{round(recent_avg/overall_avg*100)}%）→ 飽き警告")

    # 語尾の鮮度
    all_by_ending = defaultdict(list)
    for r in all_rows:
        all_by_ending[ending_of(r.get("catch", ""))].append(r.get("views", 0))
    recent_by_ending = defaultdict(list)
    for r in rows_14d:
        recent_by_ending[ending_of(r.get("catch", ""))].append(r.get("views", 0))
    for e, vs in recent_by_ending.items():
        if len(vs) > 5 and e != "(空)":
            recent_avg = sum(vs) / len(vs)
            overall_avg = sum(all_by_ending[e]) / len(all_by_ending[e]) if all_by_ending[e] else 0
            if overall_avg > 0 and recent_avg < overall_avg * 0.7:
                warnings.append(f"語尾「…{e}」: 直近14日{len(vs)}回使用・平均{int(recent_avg):,}v（全期間平均{int(overall_avg):,}vの{round(recent_avg/overall_avg*100)}%）→ 飽き警告")

    return warnings


def five_state(value: float, baseline_median: float) -> str:
    if baseline_median <= 0:
        return "判定不可（母数不足）"
    ratio = value / baseline_median
    if ratio < 0.3:
        return f"死亡圏（{ratio:.2f}倍）"
    if ratio < 0.7:
        return f"不調圏（{ratio:.2f}倍）"
    if ratio < 1.5:
        return f"通常圏（{ratio:.2f}倍）"
    if ratio < 3:
        return f"好調圏（{ratio:.2f}倍）"
    return f"バースト圏（{ratio:.2f}倍）"


def build_report() -> str:
    all_rows = load_insights()
    if not all_rows:
        return "# 週次レポート\n\nインサイトデータがありません。`pull_insights.py` を先に実行してください。\n"

    today = datetime.now(JST).date()
    last_start, last_end = week_bounds(1, today)
    prev_start, prev_end = week_bounds(2, today)
    prev2_start, prev2_end = week_bounds(3, today)

    last_week_rows = filter_week(all_rows, last_start, last_end)
    prev_week_rows = filter_week(all_rows, prev_start, prev_end)
    prev2_week_rows = filter_week(all_rows, prev2_start, prev2_end)

    cutoff_14d = (today - timedelta(days=14)).isoformat()
    rows_14d = [r for r in all_rows if r.get("date", "") >= cutoff_14d]

    iso_year, iso_week, _ = last_start.isocalendar()
    week_label = f"{iso_year}-W{iso_week:02d}"

    posted_total = count_posted_total()
    coverage = round(len(all_rows) / posted_total * 100, 1) if posted_total else 0.0

    L = []
    L.append(f"# 週次レポート {week_label}（{last_start.isoformat()}〜{last_end.isoformat()}）\n")
    L.append(f"> 生成: {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}　/ 先週分析対象: {len(last_week_rows)}件　/ 全期間: {len(all_rows)}件\n")
    L.append(f"> インサイト収集カバレッジ: 全投稿{posted_total}件中{len(all_rows)}件収集（{coverage}%）。100%未満の分は`_データ欠損メモ.md`参照。以下の集計はこのカバレッジの範囲内のサンプルであることに留意。\n")

    if not last_week_rows:
        L.append("⚠️ 先週分のデータがありません（未収集または投稿なし）。以下は全期間集計のみです。\n")

    # 1. スロット別
    L.append("## 1. スロット別成績（median<100は削除候補）\n")
    for label, rows in [("先週", last_week_rows), ("全期間", all_rows)]:
        L.append(f"### {label}\n")
        L.append("| スロット | 件数 | median | 平均 | 最大 | 削除候補 |")
        L.append("|:---:|---:|---:|---:|---:|:---:|")
        for row in build_slot_table(rows):
            flag = "🚩" if row["flag"] else ""
            L.append(f"| {row['slot']} | {row['n']} | {row['median']:,} | {row['avg']:,} | {row['max']:,} | {flag} |")
        L.append("")

    # 2. フックの型別成績
    L.append("## 2. フックの型別成績\n")
    for label, rows in [("先週", last_week_rows), ("全期間", all_rows)]:
        L.append(f"### {label}\n")
        L.append("| 型 | 件数 | 平均views | median | 平均エンゲージ率 |")
        L.append("|:---|---:|---:|---:|---:|")
        for row in build_type_table(rows):
            L.append(f"| {row['type']} | {row['n']} | {row['avg']:,} | {row['median']:,} | {row['avg_er']}% |")
        L.append("")

    # 3. テーマ別成績
    L.append("## 3. テーマ別成績（AI_RATIO判断材料）\n")
    for label, rows in [("先週", last_week_rows), ("全期間", all_rows)]:
        L.append(f"### {label}\n")
        L.append("| テーマ | 件数 | 平均views |")
        L.append("|:---|---:|---:|")
        theme_rows = build_theme_table(rows)
        for row in theme_rows:
            L.append(f"| {row['theme']} | {row['n']} | {row['avg']:,} |")
        total = sum(row["n"] for row in theme_rows)
        ai_row = next((row for row in theme_rows if row["theme"] == "AI・テック"), None)
        ai_ratio = round(ai_row["n"] / total, 3) if ai_row and total else 0.0
        L.append(f"\nAI・テック比率: {ai_ratio}（現行AI_RATIO設定と比較して判断）\n")

    # 4. ツリー長別
    L.append("## 4. ツリー長別成績\n")
    for label, rows in [("先週", last_week_rows), ("全期間", all_rows)]:
        L.append(f"### {label}\n")
        L.append("| 種別 | 件数 | 平均views |")
        L.append("|:---|---:|---:|")
        for row in build_tree_length_table(rows):
            L.append(f"| {row['label']} | {row['n']} | {row['avg']:,} |")
        L.append("")

    # 5. ホームラン監視
    L.append("## 5. 週の最大views（ホームラン）と前週比\n")
    max_last = max((r.get("views", 0) for r in last_week_rows), default=0)
    max_prev = max((r.get("views", 0) for r in prev_week_rows), default=0)
    max_prev2 = max((r.get("views", 0) for r in prev2_week_rows), default=0)
    L.append("| 週 | 最大views |")
    L.append("|:---|---:|")
    L.append(f"| 先週（{last_start}〜） | {max_last:,} |")
    L.append(f"| 先々週（{prev_start}〜） | {max_prev:,} |")
    L.append(f"| 3週前（{prev2_start}〜） | {max_prev2:,} |")
    two_week_decline = max_last < max_prev < max_prev2
    if two_week_decline:
        L.append("\n**⚠️Fable5に戻す: ホームランが2週連続で下落しています。**\n")
    else:
        L.append("")

    # 6. CTA種別成績
    L.append("## 6. CTA種別ごとの成績（2026-06-29導入CTA10種）\n")
    for label, rows in [("先週", last_week_rows), ("全期間", all_rows)]:
        L.append(f"### {label}\n")
        cta_rows = build_cta_table(rows)
        if not cta_rows:
            L.append("該当CTA投稿なし\n")
            continue
        L.append("| CTA軸 | 件数 | 平均views | 平均返信 |")
        L.append("|:---|---:|---:|---:|")
        for row in cta_rows:
            L.append(f"| {row['cta']} | {row['n']} | {row['avg_views']:,} | {row['avg_replies']} |")
        L.append("")

    # 7. LINE流入数（手動記入）
    L.append("## 7. LINE流入数（手動記入）\n")
    week_start_key = last_start.isoformat()
    ensure_line_manual_entry(week_start_key)
    line_entries = load_line_manual()
    entry = line_entries.get(week_start_key, {})
    line_val = entry.get("line_additions")
    if line_val is None:
        L.append(f"⚠️ 未記入。`{LINE_MANUAL_FILE.name}` の `week_start: {week_start_key}` にエルメ管理画面の友だち追加数を手動記入してください。\n")
    else:
        L.append(f"先週のLINE友だち追加数: **{line_val}人**\n")
        L.append("（月60アクションペース = 週あたり約14人が目安）\n")

    # 8. 鮮度トラッキング
    L.append("## 8. 鮮度トラッキング（直近14日・型/語尾の使用回数と成績推移）\n")
    warnings = freshness_check(rows_14d, all_rows)
    if warnings:
        for w in warnings:
            L.append(f"- ⚠️ {w}")
    else:
        L.append("直近14日で「飽き」判定に該当する型・語尾はありません。")
    L.append("")

    # 9. 5状態判定
    L.append("## 9. 5状態判定による週の総評\n")
    baseline_median = median([r.get("views", 0) for r in all_rows])
    last_week_avg = int(sum(r.get("views", 0) for r in last_week_rows) / len(last_week_rows)) if last_week_rows else 0
    state = five_state(last_week_avg, baseline_median)
    L.append(f"- 全期間median: {baseline_median:,}v")
    L.append(f"- 先週平均views: {last_week_avg:,}v")
    L.append(f"- 判定: **{state}**")

    return "\n".join(L)


def main():
    content = build_report()

    today = datetime.now(JST).date()
    last_start, _ = week_bounds(1, today)
    iso_year, iso_week, _ = last_start.isocalendar()
    fname = f"{iso_year}-W{iso_week:02d}.md"

    # リポジトリ内に必ず出力（クラウドの週次ルーティンはこの repo コピーを読む）
    repo_dir = BASE_DIR / "reports" / "weekly"
    repo_dir.mkdir(parents=True, exist_ok=True)
    repo_file = repo_dir / fname
    repo_file.write_text(content, encoding="utf-8")
    print(f"週次レポート生成(repo): {repo_file}")

    # Obsidian/OneDriveにもコピー（ローカルのみ。クラウド/別OSでは失敗しても続行）
    try:
        OBSIDIAN_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        obs_file = OBSIDIAN_REPORT_DIR / fname
        obs_file.write_text(content, encoding="utf-8")
        print(f"週次レポート生成(Obsidian): {obs_file}")
    except Exception as e:
        print(f"[INFO] OneDrive出力はスキップ（ローカル以外の環境）: {e}")


if __name__ == "__main__":
    main()
