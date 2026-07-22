"""
Excelシートの編集内容をposts/{date}.jsonに反映するスクリプト

使い方:
  python import_excel.py              # デスクトップの最新シートを自動検索
  python import_excel.py 2026-04-01  # 指定日だけ反映
"""

import sys
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import openpyxl

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"

DESKTOP = Path.home() / "OneDrive" / "Desktop"
if not DESKTOP.exists():
    DESKTOP = Path.home() / "Desktop"


def find_latest_sheet() -> Path:
    """デスクトップの最新のThreads確認シートを返す"""
    files = sorted(DESKTOP.glob("Threads_投稿確認シート_*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError("デスクトップにThreads_投稿確認シート_*.xlsxが見つかりません")
    return files[0]


def parse_date_label(label: str) -> str | None:
    """'03/30(月)' 形式 → '2026-03-30' に変換"""
    if not label:
        return None
    try:
        month_day = label[:5]  # 'MM/DD'
        year = datetime.now().year
        dt = datetime.strptime(f"{year}/{month_day}", "%Y/%m/%d")
        # 年またぎ対応
        if dt.month < datetime.now().month - 1:
            dt = dt.replace(year=year + 1)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def import_excel(filter_date: str = None):
    sheet_path = find_latest_sheet()
    print(f"\n読み込み: {sheet_path.name}")

    # Excelで開いていてもロックを回避するため一時コピーして読み込む
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    shutil.copy2(sheet_path, tmp_path)
    try:
        wb = openpyxl.load_workbook(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    ws = wb["投稿スケジュール"]

    # date_str → {slot: [posts]}
    schedule: dict[str, dict] = {}
    current_date = None

    for row in ws.iter_rows(min_row=2, values_only=True):
        date_label, slot, kind, cta, p1, p2, p3 = (row + (None,) * 7)[:7]

        # 日付セルが空の場合は直前の日付を継続（セル結合のため）
        if date_label:
            current_date = parse_date_label(str(date_label))

        if not current_date or not slot:
            continue

        if filter_date and current_date != filter_date:
            continue

        # 空行スキップ（投稿1が空 = 内容なし）
        if not p1:
            continue

        # 投稿リストを組み立て
        posts = [str(p1).strip()]
        if p2 and str(p2).strip():
            posts.append(str(p2).strip())
        if p3 and str(p3).strip():
            posts.append(str(p3).strip())

        schedule.setdefault(current_date, {})[str(slot)] = posts

    if not schedule:
        print("  反映対象なし（投稿1が空の行はスキップされます）")
        return

    # JSONに書き出し
    POSTS_DIR.mkdir(exist_ok=True)
    updated = []
    for date_str, slots in sorted(schedule.items()):
        out_path = POSTS_DIR / f"{date_str}.json"

        # 既存JSONがあればマージ（Excelにある分だけ上書き）
        existing = {}
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        existing.update(slots)

        # 時刻順にソート
        sorted_slots = dict(sorted(existing.items()))
        out_path.write_text(json.dumps(sorted_slots, ensure_ascii=False, indent=2), encoding="utf-8")
        updated.append(f"  {date_str}: {len(slots)} スロット反映 → {out_path.name}")

    print("\n".join(updated))
    print(f"\n完了: {len(updated)} 日分のJSONを更新しました")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    filter_date = args[0] if args else None
    import_excel(filter_date)


if __name__ == "__main__":
    main()
