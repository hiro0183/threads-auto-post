"""
IGストーリー 今週の1枚ページを生成する（2026-08-24新設）

なぜ作るか:
  IGストーリーの画像だけが「なりあいさんのPCでしか作れない」状態で残っていた。
  フォントをリポジトリへ同梱してクラウドでも描けるようにしたので、
  出来た画像を**スマホで受け取れる場所**が要る。OneDriveはPCが作らないと埋まらないため、
  週7枚を1枚のHTMLに埋め込み（データURI）、Artifactとして公開する。
  iPhoneでは画像を長押しすれば写真に保存できる。

使い方:
  python build_ig_page.py                    # 今週（直近の月曜）
  python build_ig_page.py 2026-08-24         # 指定した月曜の週
  python build_ig_page.py 2026-08-24 -o ig_page.html
"""

import argparse
import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
PLAN_DIR = BASE_DIR / "ig_stories" / "plan"
JST = timezone(timedelta(hours=9))
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


def _out_dir() -> Path:
    onedrive = Path(r"C:\Users\tujid\OneDrive\IGストーリー投稿")
    return onedrive if onedrive.exists() else BASE_DIR / "ig_stories" / "out"


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def latest_monday(today=None) -> str:
    d = today or datetime.now(JST).date()
    return (d - timedelta(days=d.weekday())).isoformat()


def load_plan(monday: str) -> dict:
    f = PLAN_DIR / f"{monday}.json"
    if not f.exists():
        raise SystemExit(f"プランがありません: {f}")
    return json.loads(f.read_text(encoding="utf-8"))


def image_data_uri(date_str: str):
    png = _out_dir() / f"{date_str}.png"
    if not png.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode("ascii")


CSS = """
:root{
  --ground:#f7f5f3; --surface:#ffffff; --ink:#1a1719; --ink-soft:#6d6469;
  --line:#e6e0dd; --accent:#8a3a56; --accent-soft:#f3e6ea; --done:#9b9298;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#111013; --surface:#1a181c; --ink:#ece7ea; --ink-soft:#a49aa1;
    --line:#2c282e; --accent:#d98aa4; --accent-soft:#2a1e24; --done:#6b636a;
  }
}
:root[data-theme="dark"]{
  --ground:#111013; --surface:#1a181c; --ink:#ece7ea; --ink-soft:#a49aa1;
  --line:#2c282e; --accent:#d98aa4; --accent-soft:#2a1e24; --done:#6b636a;
}
*{ box-sizing:border-box; }
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"Zen Kaku Gothic New","Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif;
  line-height:1.75; -webkit-text-size-adjust:100%;
}
.wrap{ max-width:560px; margin:0 auto; padding:28px 18px 64px; }

.masthead{ padding-bottom:20px; border-bottom:1px solid var(--line); margin-bottom:26px; }
.eyebrow{
  font-size:.7rem; letter-spacing:.16em; text-transform:uppercase;
  color:var(--accent); font-weight:700; margin:0 0 6px;
}
h1{
  font-family:"Zen Old Mincho",serif; font-weight:600;
  font-size:1.72rem; line-height:1.35; margin:0 0 4px; text-wrap:balance;
}
.range{ color:var(--ink-soft); font-size:.86rem; font-variant-numeric:tabular-nums; margin:0; }
.theme{ margin:14px 0 0; font-size:.88rem; color:var(--ink-soft); }

.howto{
  margin-top:20px; padding:14px 16px; background:var(--accent-soft);
  border-radius:12px; font-size:.85rem;
}
.howto b{ color:var(--accent); }
.howto ol{ margin:8px 0 0; padding-left:1.2em; }
.howto li{ margin:3px 0; }

.day{
  background:var(--surface); border:1px solid var(--line);
  border-radius:14px; overflow:hidden; margin-bottom:20px;
}
.day.past{ opacity:.5; }
.day-head{
  display:flex; align-items:baseline; gap:10px;
  padding:16px 18px 0;
}
.ord{
  font-size:.74rem; font-weight:700; color:var(--surface);
  background:var(--accent); border-radius:999px;
  min-width:22px; height:22px; display:inline-flex; align-items:center; justify-content:center;
  flex:none; font-variant-numeric:tabular-nums;
}
.date{ font-size:.84rem; color:var(--ink-soft); font-variant-numeric:tabular-nums; }
.today{
  margin-left:auto; font-size:.7rem; font-weight:700; color:var(--accent);
  border:1px solid var(--accent); border-radius:999px; padding:1px 8px;
}
.hook{
  font-family:"Zen Old Mincho",serif; font-weight:600;
  font-size:1.16rem; line-height:1.5; margin:8px 18px 14px; text-wrap:balance;
}
.shot{ display:block; width:100%; height:auto; border-top:1px solid var(--line); }
.save{
  font-size:.78rem; color:var(--ink-soft); padding:10px 18px;
  border-top:1px solid var(--line); margin:0;
}
details{ border-top:1px solid var(--line); }
summary{
  padding:11px 18px; font-size:.82rem; color:var(--ink-soft);
  cursor:pointer; list-style:none;
}
summary::-webkit-details-marker{ display:none; }
summary::before{ content:"▸ "; color:var(--accent); }
details[open] summary::before{ content:"▾ "; }
details p{
  margin:0; padding:0 18px 16px; font-size:.88rem;
  white-space:pre-wrap; color:var(--ink);
}
.photo-note{
  padding:16px 18px; font-size:.88rem; color:var(--ink-soft);
  border-top:1px solid var(--line);
}
.missing{
  padding:16px 18px; font-size:.85rem; color:var(--accent);
  border-top:1px solid var(--line);
}
footer{
  margin-top:34px; padding-top:18px; border-top:1px solid var(--line);
  font-size:.78rem; color:var(--ink-soft);
}
a{ color:var(--accent); }
:focus-visible{ outline:2px solid var(--accent); outline-offset:2px; }
"""


def build(plan: dict, monday: str) -> str:
    days = plan.get("days") or {}
    keys = sorted(days.keys())
    first, last = (keys[0], keys[-1]) if keys else (monday, monday)

    def label(d: str) -> str:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return f"{dt.month}/{dt.day}（{WEEKDAY_JP[dt.weekday()]}）"

    cards = []
    for i, d in enumerate(keys, 1):
        entry = days[d]
        kind = entry.get("type", "text")
        hook = esc(entry.get("hook") or entry.get("caption") or "")
        body = esc(entry.get("body") or "")

        if kind == "photo":
            media = (f'<p class="photo-note">📷 写真の日 — {esc(entry.get("photo_note", ""))}<br>'
                     f'添えるひとこと: {esc(entry.get("caption", ""))}</p>')
        else:
            uri = image_data_uri(d)
            if uri:
                media = (f'<img class="shot" src="{uri}" alt="{hook}" loading="lazy">'
                         f'<p class="save">画像を長押し →「写真に追加」で保存できます</p>')
            else:
                media = ('<p class="missing">画像がまだ作られていません'
                         '（Claudeに「今週のIG画像を作り直して」と伝えてください）</p>')

        detail = (f'<details><summary>本文を読む</summary><p>{body}</p></details>'
                  if body else "")

        cards.append(f"""  <article class="day" data-date="{d}">
    <div class="day-head">
      <span class="ord">{i}</span>
      <span class="date">{label(d)}</span>
    </div>
    <h2 class="hook">{hook}</h2>
    {media}
    {detail}
  </article>""")

    note = esc(plan.get("note", ""))
    theme_line = f'<p class="theme">{note}</p>' if note else ""

    return f"""<title>今週のIGストーリー</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700&family=Zen+Old+Mincho:wght@600&display=swap">
<style>{CSS}</style>

<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">Instagram Stories</p>
    <h1>今週のIGストーリー</h1>
    <p class="range">{label(first)} 〜 {label(last)}　全{len(keys)}枚</p>
    {theme_line}
    <div class="howto">
      <b>上げかた</b>
      <ol>
        <li>その日の画像を長押しして「写真に追加」</li>
        <li>Instagram → ストーリーズ → 保存した画像を選ぶ</li>
        <li>そのまま投稿（文字入れ・加工は不要です）</li>
      </ol>
    </div>
  </header>

{chr(10).join(cards)}

  <footer>
    毎週日曜の朝に、その週の7枚が自動で用意されます。<br>
    直したいときは claude.ai/code で <code>threads-auto-post</code> を選んで
    「8/27のIGストーリーを直して」と伝えてください。
  </footer>
</div>

<script>
  // 今日のカードに印を付け、過ぎた日は控えめにする（日本時間で判定）
  (function () {{
    var jst = new Date(Date.now() + (new Date().getTimezoneOffset() * 60000) + 9 * 3600000);
    var today = jst.toISOString().slice(0, 10);
    document.querySelectorAll('.day').forEach(function (el) {{
      var d = el.getAttribute('data-date');
      if (d === today) {{
        var chip = document.createElement('span');
        chip.className = 'today';
        chip.textContent = '今日';
        el.querySelector('.day-head').appendChild(chip);
      }} else if (d < today) {{
        el.classList.add('past');
      }}
    }});
  }})();
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("monday", nargs="?", help="対象週の月曜日付（省略時は今週）")
    ap.add_argument("-o", "--out", default="ig_page.html")
    args = ap.parse_args()

    monday = args.monday or latest_monday()
    plan = load_plan(monday)
    html = build(plan, monday)
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    kb = len(html.encode("utf-8")) // 1024
    print(f"生成完了: {out}（{kb} KB）")


if __name__ == "__main__":
    main()
