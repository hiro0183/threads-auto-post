"""
運用司令室（見える化ダッシュボード）生成スクリプト

「何がいつどこで動いているか」「今日人間がやることは何か」を
①ステータスカード画像（絵で一目）＋②Markdownノート（文章で詳細）の両方で
Obsidianの1枚のノートに毎朝自動で書き出す。

毎朝05:00にタスクスケジューラ（Threads_OpsDashboard）から自動実行
（04:55のヘルスチェック結果を取り込むため、その直後に実行する。
 ユーザーは5時起床・6時過ぎ外出のため、5:00までに全情報が揃っている必要がある）。

使い方: python ops_dashboard.py
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent
VAULT_CONSUL = Path(r"C:\Users\tujid\OneDrive\Desktop\HIRAYASU\コンサルThreads")
OUT_FILE = VAULT_CONSUL / "⭐運用司令室.md"
CARD_FILE = VAULT_CONSUL / "運用司令室_今朝の状態.png"
HTML_FILE = VAULT_CONSUL / "自動化オフィス.html"
HEALTH_LOG = BASE_DIR / "health_check_history.log"
FOLLOWER_LOG = BASE_DIR / "follower_log.jsonl"
POSTS_DIR = BASE_DIR / "posts"
IG_PLAN_DIR = BASE_DIR / "ig_stories" / "plan"
IG_OUT_DIR = Path(r"C:\Users\tujid\OneDrive\IGストーリー投稿")
PREVIEW_DIR = Path(r"C:\Users\tujid\OneDrive\Desktop\コンサル投稿確認")
INSIGHTS_DATA = BASE_DIR / "insights_data.jsonl"

FONT_BOLD = r"C:\Windows\Fonts\NotoSansJP-Bold.ttf"
FONT_BODY = r"C:\Windows\Fonts\meiryo.ttc"

GREEN = (34, 197, 94)
RED = (239, 68, 68)
GRAY = (107, 114, 128)
BG = (15, 17, 21)
FG = (240, 240, 240)
FG_SUB = (170, 175, 185)


# ── データ収集 ──────────────────────────────────────────

def latest_insight_date() -> str:
    if not INSIGHTS_DATA.exists():
        return "-"
    latest = ""
    for line in INSIGHTS_DATA.read_text(encoding="utf-8").strip().split("\n"):
        try:
            d = json.loads(line)
            if d.get("date", "") > latest:
                latest = d["date"]
        except Exception:
            pass
    return latest or "-"


def follower_today(today: str):
    if not FOLLOWER_LOG.exists():
        return None
    last = None
    for line in FOLLOWER_LOG.read_text(encoding="utf-8").strip().split("\n"):
        try:
            last = json.loads(line)
        except Exception:
            pass
    if last and last.get("date") == today:
        return last.get("count")
    return None


def ig_story_today(today: str):
    """今日のIGストーリー状態: (種別, 人間向け説明)"""
    png = IG_OUT_DIR / f"{today}.png"
    note = IG_OUT_DIR / f"{today}_やること.txt"
    if png.exists():
        return ("text", f"画像あり → スマホのOneDriveアプリ「IGストーリー投稿」から {today}.png をアップ")
    if note.exists():
        return ("photo", f"写真の日 → {note.name} の指示を見て写真＋ひとことをアップ")
    if IG_PLAN_DIR.exists():
        for f in IG_PLAN_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if today in (data.get("days") or {}):
                    return ("pending", "プランはあるが画像未生成（IG_StoryRenderタスクを確認）")
            except Exception:
                pass
    return (None, "今日のプランなし（月曜のFable5セッションで作成）")


def _git_commit_ts(rel_path: str):
    """リポジトリ内ファイルの最終コミットUNIX時刻。未コミットならNone"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", rel_path],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return int(out) if out else None
    except Exception:
        return None


def _git_has_local_changes(rel_path: str) -> bool:
    """未コミットの変更・未追跡ファイルがあるか（＝GitHubに届いていない）"""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", rel_path],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return bool(out)
    except Exception:
        return False


def _git_fetch() -> None:
    """origin/master を最新化（best-effort・オフラインでも落とさない）。
    このPCが同期遅れかどうかを判定する前に、GitHub本体の最新を取り込む。"""
    try:
        subprocess.run(
            ["git", "fetch", "--quiet", "origin", "master"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=45,
        )
    except Exception:
        pass


def _origin_has(rel_path: str) -> bool:
    """GitHub本体(origin/master)にそのファイルが存在するか。
    ローカルに無くても origin に有れば『未生成』ではなく『同期遅れ』と判定できる。"""
    try:
        r = subprocess.run(
            ["git", "cat-file", "-e", f"origin/master:{rel_path}"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0
    except Exception:
        return False


def _weekly_plan_for(date_str: str):
    """date_strを含む週のweekly_planファイルを返す（月曜日付ファイル名前提）"""
    plan_dir = POSTS_DIR / "weekly_plan"
    if not plan_dir.exists():
        return None
    best = None
    for f in sorted(plan_dir.glob("*.json")):
        monday = f.stem  # YYYY-MM-DD
        try:
            m = datetime.strptime(monday, "%Y-%m-%d")
        except ValueError:
            continue
        d = datetime.strptime(date_str, "%Y-%m-%d")
        if m <= d <= m + timedelta(days=6):
            best = f
    return best


def posts_freshness(date_str: str):
    """今日のThreads投稿の鮮度判定（2026-07-18新設。存在チェックだけでは
    6/30作り置きの9日間見逃し事故が再発するため、gitコミット時刻で判定する）。
    返り値: (ok: bool, 詳細メッセージ, kind)
    kind: "ok" / "not_generated"(真の未生成) / "sync_lag"(GitHubには有るがPCが遅れ) /
          "unpushed"(ローカルのみ) / "stale"(週次プランより古い)。
    kind は「今日やること」で正しい声かけ文を出すために使う。"""
    posts_file = POSTS_DIR / f"{date_str}.json"
    rel = f"posts/{date_str}.json"
    if not posts_file.exists():
        # ローカルに無くても GitHub本体に有れば『未生成』ではなく『同期遅れ』。
        # 2026-07-21: このPCが6コミット遅れで today.json をpullできず、
        # 実際は生成済みなのに「生成されていない」と誤報した事故の再発防止。
        _git_fetch()
        if _origin_has(rel):
            return (False,
                    f"GitHubには生成済み・このPCが同期遅れです（投稿は正常。Claude Codeで"
                    f"「PCをGitHubに同期して」と伝えれば追いつきます）",
                    "sync_lag")
        return (False, f"posts\\{date_str}.json がありません（生成されていない）", "not_generated")
    if _git_has_local_changes(rel):
        return (False, f"生成済みだが未push（GitHubに届いておらずRenderは古い版を投稿中）", "unpushed")
    commit_ts = _git_commit_ts(rel)
    if commit_ts is None:
        return (False, "未コミット（GitHubに届いていない）", "unpushed")
    plan_file = _weekly_plan_for(date_str)
    if plan_file is not None:
        plan_ts = _git_commit_ts(f"posts/weekly_plan/{plan_file.name}")
        if plan_ts and commit_ts < plan_ts:
            old = datetime.fromtimestamp(commit_ts).strftime("%m/%d")
            return (False, f"古い原稿（{old}コミットのまま・週次プランが反映されていない）", "stale")
    fresh = datetime.fromtimestamp(commit_ts).strftime("%m/%d %H:%M")
    return (True, f"posts\\{date_str}.json（{fresh} push済みの新原稿）", "ok")


def inspection_status(date_str: str):
    """朝の独立検品（Haiku・morning_inspection.py）の結果。
    返り値: (ok: bool|None, 詳細)"""
    f = POSTS_DIR / "quality_gate" / f"{date_str}_inspection.json"
    if not f.exists():
        return (None, "未実施（毎朝04:45に自動実行）")
    try:
        results = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return (False, "結果ファイルが読めません")
    ng = [slot for slot, r in results.items() if not r.get("ok")]
    if ng:
        return (False, f"NG {len(ng)}件: {', '.join(ng)}（中身は posts\\quality_gate\\{date_str}_inspection.json）")
    return (True, f"全{len(results)}スロット合格")


def tomorrow_status(tomorrow: str, now: datetime):
    """明日分の原稿と昼検品の状態（2026-07-18新設・昼12:00検品体制）。
    返り値: (ok: bool|None, 詳細)"""
    posts_file = POSTS_DIR / f"{tomorrow}.json"
    if not posts_file.exists():
        if _weekly_plan_for(tomorrow) is None:
            return (None, "週次プラン待ち（月曜分は当日朝06:30に自動生成）")
        if now.hour >= 7:
            return (False, "明日分の原稿が未生成（クラウド06:00便が動いていない可能性）")
        return (None, "クラウドが06:00に生成予定")
    insp_ok, insp_detail = inspection_status(tomorrow)
    if insp_ok is None:
        if now.hour >= 13:
            return (False, "原稿はあるが昼12:00の検品が未実施")
        return (None, "原稿あり・12:00に検品予定")
    return (insp_ok, f"昼検品: {insp_detail}")


def health_status():
    if not HEALTH_LOG.exists():
        return (None, "-")
    lines = HEALTH_LOG.read_text(encoding="utf-8").strip().split("\n")
    if not lines:
        return (None, "-")
    last = lines[-1]
    return ("[OK]" in last, last.split(" [")[0])


def next_monday(today_dt: datetime) -> str:
    days_ahead = (0 - today_dt.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (today_dt + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def _file_url(p) -> str:
    """ローカルHTMLから直接開ける file:// URL を作る（既存サイドバーと同方式・
    日本語パスはそのまま）。今日やることのクリックで実ファイル/フォルダへ直行するため。"""
    return "file:///" + str(p).replace("\\", "/")


def collect_data():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    hc_ok, hc_time = health_status()
    fc = follower_today(today)
    li = latest_insight_date()
    ok_insight = li >= (now - timedelta(days=3)).strftime("%Y-%m-%d")
    ig_kind, ig_detail = ig_story_today(today)
    ig_ok = ig_kind in ("text", "photo")
    today_posts_ok, posts_detail, posts_kind = posts_freshness(today)
    insp_ok, insp_detail = inspection_status(today)
    tmr_ok, tmr_detail = tomorrow_status(tomorrow, now)

    # チェック項目: (ラベル, ok(None=灰色), 詳細)
    checks = [
        ("自動タスク全体", hc_ok, f"最終チェック {hc_time}" if hc_ok is not None else "ヘルスチェック未実施"),
        ("フォロワー記録", fc is not None, f"{fc:,}人" if fc else "今日分が未記録"),
        ("インサイト収集", ok_insight, f"最新: {li}"),
        ("IGストーリー準備", ig_ok, ig_detail if ig_ok else ig_detail),
        ("今日のThreads投稿", today_posts_ok, posts_detail),
        ("今日分の検品(Haiku)", insp_ok, insp_detail),
        ("明日分の原稿と昼検品", tmr_ok, tmr_detail),
    ]

    # 今日やること: (タイトル, 詳細, リンク)。リンクはPCのHTMLでクリックすると
    # 実ファイル/フォルダへ直行する（探す手間をなくす）。ファイルを開く用事だけリンクを付け、
    # 「Claude Codeに伝える」系はリンクなし（開く対象がないため）。
    ig_week_dir = IG_OUT_DIR / "今週分"
    ig_link = _file_url(ig_week_dir if ig_week_dir.exists() else IG_OUT_DIR)
    todos = []
    todos.append(("IGストーリー投稿（1〜2分）", ig_detail, ig_link))
    preview = PREVIEW_DIR / f"{today}.txt"
    if preview.exists():
        todos.append(("今日分プレビュー確認（1分）", f"コンサル投稿確認\\{today}.txt（昨夜21:30生成・品質ゲート⚠️だけ注意）", _file_url(preview)))
    if hc_ok is False:
        todos.append(("⚠️自動化の失敗対応", "Claude Codeで「ヘルスチェックが失敗してる、調べて」と伝える", None))
    if today_posts_ok is False:
        if posts_kind == "sync_lag":
            # GitHubには原稿が有る＝投稿は正常。PCが遅れているだけなので声かけも同期に限定する。
            todos.append(("⚠️PCの同期遅れ（投稿は正常・追いつくだけ）",
                          f"Claude Codeで「PCをGitHubに同期して」と伝える（{posts_detail}）", None))
        else:
            todos.append(("⚠️Threads原稿の鮮度異常",
                          f"Claude Codeで「今日の投稿が古い/未pushと出てる、調べて」と伝える（{posts_detail}）", None))
    if insp_ok is False:
        todos.append(("⚠️今日分の検品でNGあり", f"Claude Codeで「検品NGを見せて」と伝える（{insp_detail}）", None))
    if tmr_ok is False:
        todos.append(("⚠️明日分に問題あり（夜までに直せばOK）", f"Claude Codeで「明日分の検品NGを直して」と伝える（{tmr_detail}）", None))
    if now.weekday() == 0:
        todos.append(("【月曜】自動生成された週次企画を確認（5分）", "05:10にOpus 4.8が自動で企画済み → 作業ログ「週次企画_自動実行」と weekly_plan を一瞥。⚠️があれば対応", None))

    # 部門ステータス（HTMLオフィス用）
    gate_today = (POSTS_DIR / "quality_gate" / f"{today}.json").exists()
    plan_covers_today = False
    if IG_PLAN_DIR.exists():
        for f in IG_PLAN_DIR.glob("*.json"):
            try:
                if today in (json.loads(f.read_text(encoding="utf-8")).get("days") or {}):
                    plan_covers_today = True
                    break
            except Exception:
                pass

    return {
        "now": now, "today": today, "tomorrow": tomorrow,
        "checks": checks, "todos": todos,
        "hc_ok": hc_ok, "next_monday": next_monday(now) if now.weekday() != 0 else today,
        "fc": fc, "ok_insight": ok_insight, "ig_ok": ig_ok,
        "today_posts_ok": today_posts_ok, "gate_today": gate_today,
        "insp_ok": insp_ok,
        "plan_covers_today": plan_covers_today,
    }


# ── ステータスカード画像（絵で一目） ─────────────────────────

def _strip_emoji(text: str) -> str:
    """カード用フォントで描けない絵文字類を除去"""
    return "".join(ch for ch in text if ord(ch) < 0x2600 or 0x3000 <= ord(ch) <= 0x9FFF or 0xFF00 <= ord(ch) <= 0xFFEF).strip()


def _truncate(font, text: str, max_width: int) -> str:
    text = _strip_emoji(text)
    if font.getlength(text) <= max_width:
        return text
    while text and font.getlength(text + "…") > max_width:
        text = text[:-1]
    return text + "…"


def render_status_card(data: dict) -> Path:
    W = 1200
    margin = 70
    title_f = ImageFont.truetype(FONT_BOLD, 54)
    banner_f = ImageFont.truetype(FONT_BOLD, 46)
    row_f = ImageFont.truetype(FONT_BOLD, 38)
    sub_f = ImageFont.truetype(FONT_BODY, 30, index=0)
    todo_f = ImageFont.truetype(FONT_BODY, 32, index=0)

    checks = data["checks"]
    todos = data["todos"]

    header_h = 150
    banner_h = 120
    row_h = 96
    todo_title_h = 90
    todo_h = 62
    H = header_h + banner_h + 40 + len(checks) * row_h + todo_title_h + len(todos) * todo_h + 70

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # ヘッダー
    d.text((margin, 50), f"運用司令室  {data['today']}", font=title_f, fill=FG)

    # 総合バナー
    all_ok = all(c[1] for c in checks)
    y = header_h
    banner_color = GREEN if all_ok else RED
    d.rounded_rectangle([margin, y, W - margin, y + banner_h - 20], radius=18, fill=banner_color)
    banner_text = "すべて正常です" if all_ok else "要対応があります（赤い項目を確認）"
    d.text((margin + 40, y + 22), banner_text, font=banner_f, fill=(255, 255, 255))

    # チェック行
    y += banner_h + 40
    for label, ok, detail in checks:
        color = GREEN if ok else (GRAY if ok is None else RED)
        d.ellipse([margin, y + 14, margin + 40, y + 54], fill=color)
        d.text((margin + 70, y), label, font=row_f, fill=FG)
        detail_str = _truncate(sub_f, str(detail), W - margin * 2 - 480)
        d.text((margin + 480, y + 8), detail_str, font=sub_f, fill=FG_SUB)
        y += row_h

    # 今日やること
    y += 20
    d.text((margin, y), "今日やること", font=row_f, fill=FG)
    y += todo_title_h - 20
    for i, (title, _detail, _link) in enumerate(todos, 1):
        line = _truncate(todo_f, f"{i}. {title}", W - margin * 2)
        d.text((margin + 10, y), line, font=todo_f, fill=FG)
        y += todo_h

    img.save(CARD_FILE)
    return CARD_FILE


# ── Markdownノート（文章で詳細） ────────────────────────────

def build_md(data: dict) -> str:
    now = data["now"]
    today, tomorrow = data["today"], data["tomorrow"]

    L = []
    L.append("# ⭐運用司令室")
    L.append("")
    L.append(f"> 更新: {now.strftime('%Y-%m-%d %H:%M')}（毎朝05:00に自動更新）")
    L.append("> ここだけ見れば「今日やること」と「自動化が正常か」が全部わかります")
    L.append("")
    L.append(f"![[運用司令室_今朝の状態.png|450]]")
    L.append("")
    L.append("## 🔑 このページの開き方（覚えなくてOK・ここに書いてある）")
    L.append("")
    L.append("- **PCで（会社風の画面）**: デスクトップの「**自動化オフィスを開く**」をダブルクリック（ブラウザで部門ダッシュボードが開く）")
    L.append("- **PCで（詳細テキスト）**: デスクトップの「**⭐運用司令室を開く**」をダブルクリック（Obsidianでこのページが開く）")
    L.append("- **PCで絵だけサッと**: デスクトップの「**今朝の状態カード**」をダブルクリック（画像1枚が開く）")
    L.append("- **スマホで**: OneDriveアプリ → Desktop → HIRAYASU → コンサルThreads → `運用司令室_今朝の状態.png`（外出先から確認する時はこれ）")
    L.append("")

    L.append("## 📝 今日やること（人間の作業）")
    L.append("")
    for i, (title, detail, link) in enumerate(data["todos"], 1):
        if link:
            L.append(f"{i}. **{title}**: {detail}　→ [ここをクリックで開く]({link})")
        else:
            L.append(f"{i}. **{title}**: {detail}")
    if not data["todos"]:
        L.append("何もありません（すべて自動で動いています）")
    L.append("")

    L.append("## 🤖 自動化の状態")
    L.append("")
    L.append("| 項目 | 状態 | 詳細 |")
    L.append("|:---|:---:|:---|")
    for label, ok, detail in data["checks"]:
        mark = "✅" if ok else ("⏸" if ok is None else "❌")
        L.append(f"| {label} | {mark} | {detail} |")
    L.append("")

    L.append("## ⏰ 毎日の自動スケジュール（すべて自動・人間の操作不要）")
    L.append("")
    L.append("| 時刻 | 誰が | 何を |")
    L.append("|:---|:---|:---|")
    L.append("| 04:30 | このPC | 前日の投稿データをGitHubから回収＋インサイト集計 |")
    L.append("| 04:40 | このPC | フォロワー数を記録 |")
    L.append("| 04:45 | このPC | 投稿パターン分析＋IGストーリー黒バック画像を生成＋**今日分の独立検品（Haiku）** |")
    L.append("| 月曜 06:40 | このPC | **IGストーリー1週間分を一括生成** → `OneDrive\\IGストーリー投稿\\今週分\\`（1回DL→毎日1枚アップ） |")
    L.append("| 04:50 | このPC | インサイト集計（保険の二重実行） |")
    L.append("| 04:55 | このPC | 全タスクのヘルスチェック |")
    L.append("| 05:00 | このPC | この司令室ノート＋ステータスカード画像を更新（**原稿の鮮度もここで検査**）→ 起床時に全部揃っている |")
    L.append("| 05:00〜22:00 | Render（クラウド） | Threadsへ自動投稿（1日約10本・PCが寝ていても動く） |")
    L.append("| 06:00 | claude.ai（クラウド・Sonnet） | 明日分のThreads本文生成→自己チェック→GitHubへpush |")
    L.append("| 12:00 | このPC | **明日分の昼検品（Haiku）**: NGなら午後〜夜のうちに直す（時間の余裕を作る主役の検品） |")
    L.append("| 月曜 06:30 | このPC | **月曜の空白埋め**: 週次プラン確定後に当日分を生成してpush（他の曜日は何もしない） |")
    L.append("| 23:30 | Render（クラウド） | 投稿ログをGitHubへ保存 |")
    L.append("")
    L.append("**週次**: 毎週月曜 04:50 週次レポート自動生成 → 05:10 Opus 4.8が翌週分を自動企画（Threadsフック210本＋IGストーリー7日分）→ あなたは確認のみ。※月1回のスキーム見直しだけFable 5セッションを手動起動")
    L.append(f"**次回の月曜セッション**: {data['next_monday']}")
    L.append("")

    L.append("## 📂 どこに何があるか")
    L.append("")
    L.append("| 見たいもの | 場所 |")
    L.append("|:---|:---|")
    L.append("| 今朝の状態カード（スマホでも） | `HIRAYASU\\コンサルThreads\\運用司令室_今朝の状態.png`（OneDriveアプリから見える） |")
    L.append("| 今日のIGストーリー画像 | `OneDrive\\IGストーリー投稿\\`（スマホのOneDriveアプリからも見える） |")
    L.append("| **今週分のIGストーリー（まとめDL用）** | `OneDrive\\IGストーリー投稿\\今週分\\`（月曜に7枚一括生成＋`_今週のアップ順.txt`。ここを丸ごと保存して毎日1枚アップ） |")
    L.append("| 今日のThreads投稿プレビュー | `OneDrive\\Desktop\\コンサル投稿確認\\` |")
    L.append("| 自動化の成否（詳細） | `コンサルThreads\\インサイト\\_自動実行ヘルスチェック.md` |")
    L.append("| 週次レポート | `コンサルThreads\\インサイト\\週次レポート\\` |")
    L.append("| インサイトダッシュボード | `コンサルThreads\\インサイト\\_ダッシュボード.md` |")
    L.append("| フォロワー推移 | `コンサルThreads\\フォロワー推移.md` |")
    L.append("| Threads全体設計 | `コンサルThreads\\_指示書_Threads自動化ブラッシュアップ全体設計_2026-07-07.md` |")
    L.append("| Instagram全体設計 | `コンサルThreads\\_設計図_Instagram運用_2026-07-08.md` |")

    return "\n".join(L)


# ── 自動化オフィス（会社風HTMLダッシュボード） ─────────────────

def _dept_status(state: str):
    """state: ok / ng / idle → (色, ラベル)"""
    return {
        "ok": ("#22a06b", "稼働中"),
        "ng": ("#d94f4f", "要対応"),
        "idle": ("#9a9184", "待機中"),
    }[state]


def build_html(data: dict) -> str:
    def st(ok, idle_condition=False):
        if idle_condition:
            return "idle"
        return "ok" if ok else "ng"

    depts = [
        ("データ収集部", "Insight Room", "前日の投稿データ回収・フォロワー記録・インサイト集計",
         "毎朝 04:30〜04:50", "🤖 Python", st(data["fc"] is not None and data["ok_insight"])),
        ("分析部", "Analytics Room", "投稿パターン分析・週次レポート生成（月曜）",
         "毎朝 04:45", "🤖 Python", st(data["ok_insight"])),
        ("企画戦略部", "Strategy Room", "翌週のThreadsフック210本＋IGストーリー7日分を自動企画（あなたは月曜朝に確認のみ）",
         "毎週月曜 05:10 自動", "🧠 Opus 4.8（ヘッドレス自動実行）",
         st(True, idle_condition=not data["plan_covers_today"])),
        ("執筆部", "Writing Room", "翌日分のThreads本文を生成（フックは一字も変えない）",
         "毎朝 06:00", "🤖 Sonnet（claude.aiクラウドルーティン）", st(data["today_posts_ok"])),
        ("品質管理部", "Quality Gate", "昼12:00に明日分・朝04:45に今日分を、執筆部と独立してHaikuが検品・NGは司令室に赤表示",
         "毎日 12:00＋04:45", "🤖 Haiku 4.5（サブスク実行・別呼び出し）",
         st(data["insp_ok"], idle_condition=data["insp_ok"] is None)),
        ("投稿部", "Posting Room", "Threadsへ自動投稿（1日約10本・PCが寝ていても動く）",
         "毎日 05:00〜22:00", "☁️ Render", st(data["today_posts_ok"])),
        ("IGクリエイティブ部", "Story Studio", "黒バック長文ストーリー画像を自動生成（月曜に1週間分を一括→「今週分」フォルダにまとめ）",
         "毎朝 04:45＋毎週月曜 06:40", "🤖 Python", st(data["ig_ok"], idle_condition=not data["plan_covers_today"] and not data["ig_ok"])),
        ("監査部", "Audit Room", "全部門の成否チェック・この司令室の自動更新",
         "毎朝 04:55〜05:00", "🤖 PowerShell ＋ Python", st(bool(data["hc_ok"]))),
    ]

    n_ng = sum(1 for d in depts if d[5] == "ng")
    n_active = sum(1 for d in depts if d[5] == "ok")

    cards_html = ""
    for name, en, desc, sched, member, state in depts:
        color, label = _dept_status(state)
        pulse = ' pulse' if state == "ok" else ''
        cards_html += f"""
        <div class="card" style="border-color:{color}55">
          <div class="card-head">
            <span class="dept"><span class="dot{pulse}" style="background:{color}"></span>{name}</span>
            <span class="badge" style="background:{color}">{label}</span>
          </div>
          <div class="en">{en}</div>
          <div class="desc">{desc}</div>
          <div class="meta">👥 {member}</div>
          <div class="meta">🕐 {sched}</div>
        </div>"""

    todos_html = ""
    for i, (title, detail, link) in enumerate(data["todos"], 1):
        if link:
            todos_html += (f'<li><a class="todo-link" href="{link}">'
                           f'<b>{title}</b> <span class="open-tag">▶ クリックで開く</span>'
                           f'<span class="todo-detail">{detail}</span></a></li>')
        else:
            todos_html += f'<li><b>{title}</b><span class="todo-detail">{detail}</span></li>'
    if not data["todos"]:
        todos_html = "<li>何もありません（すべて自動で動いています）</li>"

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<title>ヒロ先生 自動化オフィス</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="600">
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Hiragino Sans", "Yu Gothic UI", "Meiryo", sans-serif;
         background: #efe8d8; color: #4a4238; margin: 0; display: flex; min-height: 100vh; }}
  .sidebar {{ width: 225px; background: #e5dcc6; padding: 24px 0; flex-shrink: 0; }}
  .brand {{ padding: 0 22px 18px; border-bottom: 1px solid #d4c8ab; margin-bottom: 12px; }}
  .brand .name {{ font-weight: bold; font-size: 16px; color: #5c4a32; }}
  .brand .powered {{ font-size: 10.5px; color: #a2957c; margin-top: 2px; }}
  .nav a {{ display: block; padding: 11px 22px; color: #6b5f4c; text-decoration: none;
            font-size: 13.5px; }}
  .nav a:hover {{ background: #dbd0b4; }}
  .nav a.active {{ background: #b5763a; color: #fff; border-radius: 0 999px 999px 0;
                   margin-right: 14px; }}
  .main {{ flex: 1; padding: 30px 36px; }}
  .header {{ display: flex; align-items: baseline; gap: 16px; margin-bottom: 22px; }}
  h1 {{ font-size: 22px; margin: 0; color: #5c4a32; }}
  .sub {{ color: #9a8f7d; font-size: 12.5px; }}
  .stats {{ display: flex; gap: 14px; margin-bottom: 24px; flex-wrap: wrap; }}
  .stat {{ background: #faf6ec; border: 1px solid #ddd2bd; border-radius: 12px;
           padding: 13px 22px; min-width: 150px; }}
  .stat .num {{ font-size: 25px; font-weight: bold; color: #5c4a32; }}
  .stat .label {{ font-size: 11.5px; color: #9a8f7d; }}
  .stat.alert .num {{ color: #d94f4f; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(235px, 1fr)); gap: 15px; }}
  .card {{ background: #fbf7ee; border: 2px solid; border-radius: 14px; padding: 15px 17px; }}
  .card-head {{ display: flex; justify-content: space-between; align-items: center; }}
  .dept {{ font-weight: bold; font-size: 14.5px; color: #4a4238; display: flex; align-items: center; gap: 7px; }}
  .dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
  .dot.pulse {{ animation: pulse 2s infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}
  .badge {{ color: #fff; font-size: 10.5px; padding: 3px 10px; border-radius: 999px; flex-shrink: 0; }}
  .en {{ color: #b0a48e; font-size: 10.5px; margin: 2px 0 8px; }}
  .desc {{ font-size: 12px; line-height: 1.65; margin-bottom: 9px; min-height: 3.2em; }}
  .meta {{ font-size: 11px; color: #8d8271; margin-top: 3px; }}
  .todos {{ background: #faf6ec; border: 1px solid #ddd2bd; border-radius: 14px;
            padding: 17px 26px; margin-top: 24px; }}
  .todos h2 {{ font-size: 15px; margin: 0 0 10px; color: #5c4a32; }}
  .todos li {{ margin-bottom: 10px; font-size: 13.5px; }}
  .todo-detail {{ display: block; font-size: 11.5px; color: #9a8f7d; margin-top: 1px; }}
  .todo-link {{ display: block; text-decoration: none; color: inherit; background: #f3ecdb;
               border: 1px solid #e0d5bb; border-radius: 10px; padding: 9px 13px; transition: background .15s; }}
  .todo-link:hover {{ background: #eadfc4; }}
  .open-tag {{ font-size: 10.5px; color: #fff; background: #b5763a; border-radius: 999px;
              padding: 2px 8px; margin-left: 6px; white-space: nowrap; }}
  .footer {{ margin-top: 22px; font-size: 11px; color: #a99e8b; }}
</style></head><body>
  <nav class="sidebar">
    <div class="brand">
      <div class="name">ヒロ先生 自動化オフィス</div>
      <div class="powered">powered by Claude</div>
    </div>
    <div class="nav">
      <a class="active" href="#">🏢 ダッシュボード</a>
      <a href="obsidian://open?vault=HIRAYASU&file=%E3%82%B3%E3%83%B3%E3%82%B5%E3%83%ABThreads%2F%E2%AD%90%E9%81%8B%E7%94%A8%E5%8F%B8%E4%BB%A4%E5%AE%A4">⭐ 運用司令室（詳細）</a>
      <a href="file:///C:/Users/tujid/OneDrive/Desktop/コンサル投稿確認/">📄 投稿プレビュー</a>
      <a href="file:///C:/Users/tujid/OneDrive/IGストーリー投稿/今週分/">📸 今週分IGストーリー（まとめ）</a>
      <a href="file:///C:/Users/tujid/OneDrive/IGストーリー投稿/">🗂 IGストーリー画像（全部）</a>
      <a href="file:///C:/Users/tujid/OneDrive/Desktop/HIRAYASU/コンサルThreads/インサイト/週次レポート/">📊 週次レポート</a>
      <a href="file:///C:/Users/tujid/OneDrive/Desktop/HIRAYASU/コンサルThreads/作業ログ/">📁 作業ログ</a>
    </div>
  </nav>
  <div class="main">
  <div class="header">
    <h1>ダッシュボード</h1>
    <span class="sub">更新: {data['now'].strftime('%Y-%m-%d %H:%M')}（毎朝05:00・毎晩21:30すぎ・月曜05:10すぎに自動更新／この画面も10分ごとに自動再読込）</span>
  </div>
  <div class="stats">
    <div class="stat"><div class="num">{n_active}<span style="font-size:14px">/{len(depts)}</span></div><div class="label">稼働部門</div></div>
    <div class="stat"><div class="num">約10</div><div class="label">本日の自動投稿（Threads）</div></div>
    <div class="stat"><div class="num">{len(data['todos'])}</div><div class="label">今日やること</div></div>
    <div class="stat{' alert' if n_ng else ''}"><div class="num">{n_ng}</div><div class="label">要対応</div></div>
  </div>
  <div class="grid">{cards_html}
  </div>
  <div class="todos">
    <h2>📝 今日やること（あなたの仕事はこれだけ）</h2>
    <ol>{todos_html}</ol>
  </div>
  <div class="footer">
    スマホ用カード: OneDriveアプリ → Desktop → HIRAYASU → コンサルThreads → 運用司令室_今朝の状態.png ／ 次回の月曜自動企画: {data['next_monday']} 05:10
  </div>
  </div>
</body></html>"""


def main():
    data = collect_data()
    card = render_status_card(data)
    OUT_FILE.write_text(build_md(data), encoding="utf-8")
    HTML_FILE.write_text(build_html(data), encoding="utf-8")
    print(f"運用司令室を更新: {OUT_FILE}")
    print(f"ステータスカード: {card}")
    print(f"自動化オフィス(HTML): {HTML_FILE}")


if __name__ == "__main__":
    main()
