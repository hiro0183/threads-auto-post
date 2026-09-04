"""小川さんの脳みそ（Obsidian）から「題材の棚」を抜き出して repo に置く。

2026-09-05新設。背景:
  `prompts/hook_rules.md` は「毎週同じ題材に戻るのは引き出しが少ないため。
  Obsidian `📚_マーケッター小川さんの脳みそ/00_運用ガイド/ナレッジベース/
  販売用ナレッジ拡張_2026-06-30/` の見出しを題材の棚として使う」と指示していた。
  ところが**週次企画はclaude.aiのクラウドルーティンで動くため、ローカルのOneDrive
  vaultには物理的に届かない**。1,148ファイルある脳みそのうち、企画が実際に読めていたのは0件。
  指示だけがあって実行できない状態が続いていた。

  そこで見出しと要点の一文だけを抜き、repoの `prompts/theme_shelf.md` に置く。
  repoならクラウドルーティンも日次実行者も読める。本文は読ませない
  （テンプレート量産で内容が薄い、と hook_rules.md 自身が書いている）。

このスクリプトはPCでしか動かない（vaultがローカルにあるため）。
棚を更新したくなったら手で回す。月1回のスキーム見直しのタイミングで十分。

使い方:
    python build_theme_shelf.py
    python build_theme_shelf.py --check   # 差分があるかだけ見る
"""
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
VAULT = Path(
    r"C:\Users\tujid\OneDrive\Desktop\HIRAYASU\📚_マーケッター小川さんの脳みそ"
    r"\00_運用ガイド\ナレッジベース\販売用ナレッジ拡張_2026-06-30"
)
OUT = BASE / "prompts" / "theme_shelf.md"

# 「〇〇の核心は、△△。という一点にある」から △△ だけを取る
CORE = re.compile(r"の核心は、(.+?)。?\s*という一点にある")


def extract(md: str) -> tuple:
    """(見出し, 要点の一文) を返す"""
    title = ""
    for line in md.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    body = md.split("## 要点", 1)
    if len(body) < 2:
        return title, ""
    para = ""
    for line in body[1].splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            break
        para = line
        break

    m = CORE.search(para)
    point = m.group(1).strip() if m else para.split("。")[0].strip()
    return title, point


def build() -> str:
    L = []
    L.append("# 題材の棚（小川さんの脳みそ 抜粋・自動生成）\n")
    L.append("> **これは `build_theme_shelf.py` が自動生成したファイル。手で編集しない。**")
    L.append("> 元: Obsidian `📚_マーケッター小川さんの脳みそ/00_運用ガイド/ナレッジベース/販売用ナレッジ拡張_2026-06-30/`")
    L.append(">")
    L.append("> **使い方（`hook_rules.md` の指示どおり）:** 毎週同じ題材に戻らないための引き出し。")
    L.append("> **使うのは見出しと要点の一文だけ。**元ノートの本文はテンプレート量産で内容が薄いので読まなくてよい。")
    L.append("> ここから題材を選んだら、**必ず読者（月商100万円以上・自費中心・売上は伸びているが時間がない治療院経営者）の場面に翻訳する。**")
    L.append("> マーケティング用語のまま投稿しない。翻訳できない題材は使わない。\n")

    total = 0
    for cat in sorted(p for p in VAULT.iterdir() if p.is_dir()):
        items = []
        for f in sorted(cat.glob("*.md")):
            if f.name.startswith("00_"):      # MOC・INDEXは飛ばす
                continue
            title, point = extract(f.read_text(encoding="utf-8"))
            if not title:
                continue
            items.append((title, point))
        if not items:
            continue
        L.append(f"## {cat.name}\n")
        for title, point in items:
            L.append(f"- **{title}** — {point}" if point else f"- **{title}**")
        L.append("")
        total += len(items)

    L.append(f"\n---\n\n合計 {total} 題材。")
    return "\n".join(L)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not VAULT.exists():
        print(f"[エラー] 脳みそが見つかりません（PCでのみ実行できます）: {VAULT}")
        return 1
    content = build()
    if "--check" in sys.argv:
        old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        print("差分あり" if old != content else "差分なし")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    n = content.count("\n- **")
    print(f"題材の棚を生成: {OUT}（{n}題材 / {len(content):,}文字）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
