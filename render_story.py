"""
IGストーリー用の黒バック長文画像を自動生成するスクリプト

ig_stories/plan/*.json（週次プラン）から当日分を読み、
1080x1920の黒背景PNG（フック大・本文中サイズ）をレンダリングして
OneDriveの「IGストーリー投稿」フォルダに保存する。
写真日（type=photo）は画像を作らず、指示テキストのみ出力する。

毎朝04:45にタスクスケジューラ（IG_StoryRender）から自動実行。

使い方:
  python render_story.py               # 今日分
  python render_story.py 2026-07-09   # 指定日
  python render_story.py week          # 今週分(月〜日)を一括生成＋「今週分」フォルダに集約
  python render_story.py week 2026-07-20  # 指定した月曜の週を一括生成
"""

import sys
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent
PLAN_DIR = BASE_DIR / "ig_stories" / "plan"
OUT_DIR = Path(r"C:\Users\tujid\OneDrive\IGストーリー投稿")

W, H = 1080, 1920
MARGIN_X = 90
HOOK_FONT_PATH = r"C:\Windows\Fonts\NotoSansJP-Bold.ttf"
BODY_FONT_PATH = r"C:\Windows\Fonts\meiryo.ttc"

BG_COLOR = (10, 10, 10)
HOOK_COLOR = (255, 255, 255)
BODY_COLOR = (228, 228, 228)
RULE_COLOR = (90, 90, 90)


def find_plan_for_date(date_str: str):
    if not PLAN_DIR.exists():
        return None
    for f in sorted(PLAN_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        days = data.get("days") or {}
        if date_str in days:
            return days[date_str]
    return None


def wrap_text(text: str, font, max_width: int) -> list[str]:
    """ピクセル幅ベースで日本語テキストを折り返す（既存の改行は維持）"""
    lines = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        current = ""
        for ch in para:
            if font.getlength(current + ch) > max_width:
                lines.append(current)
                current = ch
            else:
                current += ch
        if current:
            lines.append(current)
    return lines


def render_text_story(date_str: str, hook: str, body: str) -> Path:
    max_text_width = W - MARGIN_X * 2

    hook_size = 66
    body_size = 46

    # 収まらなければ本文フォントを段階的に縮小
    while body_size >= 34:
        hook_font = ImageFont.truetype(HOOK_FONT_PATH, hook_size)
        body_font = ImageFont.truetype(BODY_FONT_PATH, body_size, index=0)

        hook_lines = wrap_text(hook, hook_font, max_text_width)
        body_lines = wrap_text(body, body_font, max_text_width)

        hook_lh = int(hook_size * 1.45)
        body_lh = int(body_size * 1.7)

        total_h = len(hook_lines) * hook_lh + 70 + len(body_lines) * body_lh
        if total_h <= H - 480:  # 上下の余白を確保
            break
        body_size -= 2
    else:
        print(f"[警告] {date_str}: 本文が長すぎます（{len(body)}字）。フォント34pxでも収まりません。本文を短くしてください")

    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    content_h = len(hook_lines) * hook_lh + 70 + len(body_lines) * body_lh
    y = max(240, (H - content_h) // 2 - 60)

    for line in hook_lines:
        draw.text((MARGIN_X, y), line, font=hook_font, fill=HOOK_COLOR)
        y += hook_lh

    # フックと本文の間に区切り線
    y += 20
    draw.line([(MARGIN_X, y), (MARGIN_X + 160, y)], fill=RULE_COLOR, width=4)
    y += 50

    for line in body_lines:
        draw.text((MARGIN_X, y), line, font=body_font, fill=BODY_COLOR)
        y += body_lh

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{date_str}.png"
    img.save(out_path)
    return out_path


def write_note(date_str: str, lines: list[str]):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    note_path = OUT_DIR / f"{date_str}_やること.txt"
    note_path.write_text("\n".join(lines), encoding="utf-8-sig")
    return note_path


WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]
WEEK_DIR = OUT_DIR / "今週分"


def render_one(date_str: str):
    """1日分をレンダリング。返り値: (種別, 出力Path or None, hook)。
    daily の main() とロジックを共有し、週まとめから再利用する。"""
    entry = find_plan_for_date(date_str)
    if not entry:
        return ("none", None, "")
    if entry.get("type") == "photo":
        note = write_note(date_str, [
            f"【{date_str} IGストーリー】今日は写真の日です",
            "",
            f"写真: {entry.get('photo_note', '写真ストックから1枚選ぶ')}",
            f"添える文: {entry.get('caption', '')}",
            "",
            "写真ストック: OneDrive\\IGストーリー投稿\\写真ストック\\",
        ])
        return ("photo", note, entry.get("caption", ""))
    hook = entry.get("hook", "")
    body = entry.get("body", "")
    if not hook or not body:
        print(f"[エラー] {date_str}: hook/bodyが空です")
        return ("error", None, "")
    out = render_text_story(date_str, hook, body)
    write_note(date_str, [
        f"【{date_str} IGストーリー】",
        "",
        f"1. スマホのOneDriveアプリで {out.name} を開く",
        "2. そのままInstagramストーリーズにアップ（スタンプ・文字追加は不要）",
        "",
        "--- 内容（確認用） ---",
        hook,
        "",
        body,
    ])
    return ("text", out, hook)


def week_monday(date_str: str | None) -> datetime:
    """引数が月曜日付ならそれを、無ければ今日を含む週の月曜を返す。"""
    if date_str:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        d = datetime.now()
    return d - timedelta(days=d.weekday())


def render_week(monday_arg: str | None):
    """月曜起点で7日分を一括レンダリングし、『今週分』フォルダに
    アップ順の連番PNG＋アップ順リストを集約する（1回DL→毎日1枚アップ運用）。"""
    monday = week_monday(monday_arg)
    dates = [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    # 『今週分』フォルダは残したまま中身だけ入れ替える。
    # （フォルダごと削除して作り直すとスマホのお気に入り/ショートカットのリンクが
    #  週替わりで切れてしまうため。先週分の画像は下のループで消してから入れ直す）
    WEEK_DIR.mkdir(parents=True, exist_ok=True)
    for old in WEEK_DIR.iterdir():
        try:
            old.unlink()
        except Exception:
            pass

    index = [
        f"【今週のIGストーリー】{dates[0]}（月）〜{dates[6]}（日）",
        "",
        "使い方: このフォルダの画像をまとめてスマホに保存し、下の順番で毎日1枚ずつ",
        "Instagramストーリーズにアップしてください（そのまま上げるだけでOK）。",
        "",
        "──────────── アップ順 ────────────",
    ]
    made = 0
    for i, date_str in enumerate(dates):
        kind, out, hook = render_one(date_str)
        wd = WEEKDAY_JP[i]
        label = f"{i+1}日目  {date_str}（{wd}）"
        if kind == "text" and out:
            seq_name = f"{i+1}_{wd}_{date_str}.png"
            shutil.copy(out, WEEK_DIR / seq_name)
            index.append(f"{label} → {seq_name}")
            index.append(f"        フック: {hook}")
            made += 1
        elif kind == "photo":
            index.append(f"{label} → ★写真の日（{out.name} の指示を見て手持ち写真をアップ）")
        else:
            index.append(f"{label} → （プラン未作成・スキップ）")
        index.append("")

    (WEEK_DIR / "_今週のアップ順.txt").write_text("\n".join(index), encoding="utf-8-sig")
    print(f"今週分を一括生成: {made}枚 → {WEEK_DIR}")
    print(f"アップ順リスト: {WEEK_DIR / '_今週のアップ順.txt'}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args and args[0] == "week":
        render_week(args[1] if len(args) > 1 else None)
        return

    date_str = args[0] if args else datetime.now().strftime("%Y-%m-%d")

    entry = find_plan_for_date(date_str)
    if not entry:
        print(f"[スキップ] {date_str} のストーリープランがありません（ig_stories/plan/ を確認。月曜のFable5セッションで作成されます）")
        return

    if entry.get("type") == "photo":
        note = write_note(date_str, [
            f"【{date_str} IGストーリー】今日は写真の日です",
            "",
            f"写真: {entry.get('photo_note', '写真ストックから1枚選ぶ')}",
            f"添える文: {entry.get('caption', '')}",
            "",
            "写真ストック: OneDrive\\IGストーリー投稿\\写真ストック\\",
        ])
        print(f"写真日の指示を出力: {note}")
        return

    hook = entry.get("hook", "")
    body = entry.get("body", "")
    if not hook or not body:
        print(f"[エラー] {date_str}: hook/bodyが空です")
        return

    out = render_text_story(date_str, hook, body)
    write_note(date_str, [
        f"【{date_str} IGストーリー】",
        "",
        f"1. スマホのOneDriveアプリで {out.name} を開く",
        "2. そのままInstagramストーリーズにアップ（スタンプ・文字追加は不要）",
        "",
        "--- 内容（確認用） ---",
        hook,
        "",
        body,
    ])
    print(f"生成完了: {out}")


if __name__ == "__main__":
    main()
