"""
インサイトダッシュボードを生成するスクリプト

insights_data.jsonl を読み込んで、Obsidianの「コンサルThreads/インサイト/_ダッシュボード.md」に
期間別サマリー・日別トレンド・テーマ別パフォーマンス・上位投稿などを書き出す。

使い方:
  python generate_dashboard.py
  （pull_insights.py の最後でも自動実行される）
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent
INSIGHTS_DATA_FILE = BASE_DIR / "insights_data.jsonl"
OBSIDIAN_DIR = Path(r"C:\Users\tujid\OneDrive\Desktop\HIRAYASU\コンサルThreads\インサイト")
DASHBOARD_FILE = OBSIDIAN_DIR / "_ダッシュボード.md"

JST = timezone(timedelta(hours=9))


THEME_PATTERNS = [
    ("スタッフ・採用",  r"スタッフ|雇|採用|離職|人件費|給与|面接|定着"),
    ("廃業・閉院",      r"廃業|閉院|赤字|詰[まみ]|頭おかしい|やめ|潰れ|危機|借金"),
    ("ホットペッパー",  r"ホットペッパー|HPB|クーポン"),
    ("SNS発信",         r"Instagram|Threads|SNS|フォロワー|投稿|発信|リール|ストーリーズ|DM"),
    ("売上・価格",      r"売上|単価|値上げ|月商|価格|自費|メニュー|松竹梅|初診料"),
    ("LINE・CRM",       r"LINE|配信|セグメント|公式|ステップ"),
    ("リピート・失客",  r"リピート|失客|来なくなる|再来|次回予約|通[いう]"),
    ("AI・テック",      r"AI|ChatGPT|Claude|46歳|アラフィフ|自動化|広告費"),
    ("Google・MEO",     r"Google|MEO|マップ|口コミ|クチコミ"),
    ("夫婦・一人経営",  r"夫婦|一人|孤独|燃え尽き|妻|夫"),
    ("集客全般",        r"紹介|集客|新規|来院|信頼"),
]


def classify_theme(catch: str) -> str:
    """1投稿目のキャッチをテーマに分類"""
    if not catch:
        return "その他"
    for label, pattern in THEME_PATTERNS:
        if re.search(pattern, catch):
            return label
    return "その他"


def eng_rate(r: dict) -> float:
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
                continue
            seen_ids.add(rid)
            if isinstance(row.get("views"), int) and (row.get("views") or 0) > 0:
                rows.append(row)
        except Exception:
            pass
    return rows


def period_stats(rows: list, days: int = None, label: str = "全期間") -> dict:
    """指定期間の統計を返す"""
    if days is not None:
        today = datetime.now(JST).date()
        cutoff = today - timedelta(days=days)
        rs = [r for r in rows if r.get("date", "") >= cutoff.isoformat()]
    else:
        rs = rows

    if not rs:
        return {
            "label": label, "n": 0, "avg_views": 0, "max_views": 0,
            "tree_n": 0, "tree_avg": 0, "tree_max": 0,
            "single_n": 0, "single_avg": 0, "single_max": 0,
            "avg_replies": 0,
        }

    views = [r.get("views", 0) for r in rs]
    tree = [r for r in rs if r.get("post_type") == "tree"]
    single = [r for r in rs if r.get("post_type") != "tree"]
    tree_views = [r.get("views", 0) for r in tree]
    single_views = [r.get("views", 0) for r in single]

    return {
        "label": label,
        "n": len(rs),
        "avg_views": int(sum(views) / len(views)),
        "max_views": max(views),
        "tree_n": len(tree),
        "tree_avg": int(sum(tree_views) / len(tree)) if tree else 0,
        "tree_max": max(tree_views) if tree else 0,
        "single_n": len(single),
        "single_avg": int(sum(single_views) / len(single)) if single else 0,
        "single_max": max(single_views) if single else 0,
        "avg_replies": round(sum(r.get("replies", 0) or 0 for r in rs) / len(rs), 1),
    }


def daily_trend(rows: list, days: int = 14) -> list:
    """日別の統計（直近N日）"""
    by_date = defaultdict(list)
    for r in rows:
        d = r.get("date", "")
        if d:
            by_date[d].append(r)
    sorted_dates = sorted(by_date.keys())[-days:]
    result = []
    for d in sorted_dates:
        rs = by_date[d]
        views = [r.get("views", 0) for r in rs]
        replies = sum(r.get("replies", 0) or 0 for r in rs)
        result.append({
            "date": d,
            "n": len(rs),
            "avg_views": int(sum(views) / len(views)) if views else 0,
            "max_views": max(views) if views else 0,
            "total_replies": replies,
        })
    return result


def theme_stats(rows: list) -> list:
    """テーマ別の統計"""
    by_theme = defaultdict(list)
    for r in rows:
        theme = classify_theme(r.get("catch", ""))
        by_theme[theme].append(r)

    result = []
    for theme, rs in by_theme.items():
        views = [r.get("views", 0) for r in rs]
        result.append({
            "theme": theme,
            "n": len(rs),
            "avg_views": int(sum(views) / len(views)),
            "max_views": max(views),
            "avg_er": round(sum(eng_rate(r) for r in rs) / len(rs), 2),
        })
    return sorted(result, key=lambda x: -x["avg_views"])


def build_dashboard(rows: list) -> str:
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    if not rows:
        return f"# インサイトダッシュボード\n\n> 更新: {now_str}\n\nデータがまだありません。\n`python pull_insights.py` を実行してください。\n"

    periods = [
        period_stats(rows, days=7,  label="直近7日"),
        period_stats(rows, days=14, label="直近14日"),
        period_stats(rows, days=30, label="直近30日"),
        period_stats(rows, days=None, label="全期間"),
    ]
    trend = daily_trend(rows, days=14)
    themes = theme_stats(rows)

    # Top 10 全期間
    top10 = sorted(rows, key=lambda r: r.get("views", 0), reverse=True)[:10]

    # 直近7日 Top 5
    today = datetime.now(JST).date()
    recent7_cutoff = (today - timedelta(days=7)).isoformat()
    recent7 = [r for r in rows if r.get("date", "") >= recent7_cutoff]
    top5_recent = sorted(recent7, key=lambda r: r.get("views", 0), reverse=True)[:5]

    L = []
    L.append(f"# インサイトダッシュボード\n")
    L.append(f"> 更新: {now_str}　/ 分析対象: 全{len(rows)}投稿\n")

    # 期間別サマリー
    L.append("## 📊 期間別サマリー\n")
    L.append("| 期間 | 件数 | 平均views | 最大views | ツリー平均 | 単体平均 | 単体差 | 平均返信 |")
    L.append("|:---|---:|---:|---:|---:|---:|---:|---:|")
    for p in periods:
        ratio = f"{p['tree_avg'] // p['single_avg']}倍" if p['single_avg'] > 0 else "∞"
        L.append(f"| {p['label']} | {p['n']} | {p['avg_views']:,} | {p['max_views']:,} | {p['tree_avg']:,} ({p['tree_n']}) | {p['single_avg']:,} ({p['single_n']}) | {ratio} | {p['avg_replies']} |")

    # 日別トレンド
    L.append("\n## 📈 日別トレンド（直近14日）\n")
    L.append("| 日付 | 件数 | 平均views | 最大views | 返信総数 |")
    L.append("|:---:|---:|---:|---:|---:|")
    for t in trend:
        L.append(f"| {t['date']} | {t['n']} | {t['avg_views']:,} | {t['max_views']:,} | {t['total_replies']} |")

    # テーマ別パフォーマンス
    L.append("\n## 🏷️ テーマ別パフォーマンス（全期間）\n")
    L.append("| テーマ | 件数 | 平均views | 最大views | 平均エンゲージ率 |")
    L.append("|:---|---:|---:|---:|---:|")
    for t in themes:
        L.append(f"| {t['theme']} | {t['n']} | {t['avg_views']:,} | {t['max_views']:,} | {t['avg_er']}% |")

    # Top 10
    L.append("\n## 🏆 Top 10（全期間・views順）\n")
    L.append("| # | 日付 | 時刻 | 種別 | views | 返信 | テーマ | キャッチ |")
    L.append("|:---:|:---:|:---:|:---:|---:|---:|:---|:---|")
    for i, r in enumerate(top10, 1):
        ptype = "ツリー" if r.get("post_type") == "tree" else "単体"
        catch = (r.get("catch") or "")[:35]
        theme = classify_theme(r.get("catch", ""))
        L.append(f"| {i} | {r.get('date','')} | {r.get('slot','')} | {ptype} | {r.get('views',0):,} | {r.get('replies',0) or 0} | {theme} | {catch} |")

    # 直近7日 Top 5
    if top5_recent:
        L.append("\n## 🔥 直近7日のTop 5\n")
        L.append("| # | 日付 | 時刻 | 種別 | views | 返信 | テーマ | キャッチ |")
        L.append("|:---:|:---:|:---:|:---:|---:|---:|:---|:---|")
        for i, r in enumerate(top5_recent, 1):
            ptype = "ツリー" if r.get("post_type") == "tree" else "単体"
            catch = (r.get("catch") or "")[:35]
            theme = classify_theme(r.get("catch", ""))
            L.append(f"| {i} | {r.get('date','')} | {r.get('slot','')} | {ptype} | {r.get('views',0):,} | {r.get('replies',0) or 0} | {theme} | {catch} |")

    # 重要マイルストーン
    L.append("\n## 📌 重要マイルストーン\n")
    L.append("| 日付 | 出来事 | コミット |")
    L.append("|:---:|:---|:---|")
    L.append("| 2026-04-27 | インサイト分析・GitHub同期構築 | — |")
    L.append("| 2026-05-01 | プロンプト強化（バズパターン追加） | — |")
    L.append("| 2026-05-14 | コメント誘導5スロット追加 | `08cf016` |")
    L.append("| 2026-05-22 | 問題コミット（リミックス指示） | `9f84f3e` |")
    L.append("| 2026-05-25 | コメント誘導5スロット削除 | `19d56ff` |")
    L.append("| 2026-05-25 | 全ツリー化＋プロンプト修正 | （TODO） |")

    # 関連ファイル
    L.append("\n## 🔗 関連ファイル\n")
    L.append("- [[_引継ぎプロンプト_コンサルThreads]] — プロジェクト引継ぎ")
    L.append("- [[作業ログ/2026-05-25_インプ低下の原因特定とコメント誘導スロット削除]] — 直近の作業")
    L.append("- 投稿パターン分析: `投稿パターン/高エンゲージ投稿パターン.md`")
    L.append("- 日次インサイト: `インサイト/YYYY-MM-DD.md`")

    return "\n".join(L)


def main():
    rows = load_insights()
    if not rows:
        print("インサイトデータがありません。`pull_insights.py` を先に実行してください")
        return

    OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)
    content = build_dashboard(rows)
    DASHBOARD_FILE.write_text(content, encoding="utf-8")
    print(f"ダッシュボード更新: {DASHBOARD_FILE}")
    print(f"  分析対象: {len(rows)}件")


if __name__ == "__main__":
    main()
