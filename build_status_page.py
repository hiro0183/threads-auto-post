"""
運用司令室 まとめページ（Artifact用HTML）生成スクリプト

コンサル垢・ラポール垢それぞれの status_snapshot.json（ops_dashboard.py /
rapport_ops_dashboard.py が毎朝出力）を読み、スマホで1枚のURLから見られる
まとめページのHTMLを組み立てる。

claude.aiのクラウドルーティン（毎朝07:15）が両リポジトリをcloneし、
このスクリプトを実行 → 生成されたHTMLをArtifactとして同じURLに再publishする。

使い方:
  python build_status_page.py <コンサル垢のstatus_snapshot.json> <ラポール垢のstatus_snapshot.json> -o status_page.html
"""

import argparse
import json
from pathlib import Path

ACCENT = {
    "コンサル垢": ("var(--consult)", "var(--consult-soft)"),
    "ラポール垢": ("var(--rapport)", "var(--rapport-soft)"),
}

CSS = """
  :root{
    --paper:#eef1ec; --surface:#ffffff; --ink:#1d2420; --ink-soft:#586158; --line:#d9ded7;
    --consult:#2c3e6b; --consult-soft:#e7eaf3; --rapport:#8b4a5f; --rapport-soft:#f3e6ea;
    --ok:#2f855a; --ok-soft:#e4f2ea; --warn:#b7791f; --warn-soft:#faf1de;
    --critical:#c0392b; --critical-soft:#fbe7e4;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --paper:#15181a; --surface:#1d2124; --ink:#e9ece8; --ink-soft:#a3ac9f; --line:#33383a;
      --consult:#8fa3d6; --consult-soft:#232a3c; --rapport:#d998a9; --rapport-soft:#332529;
      --ok:#5cc491; --ok-soft:#1c2e26; --warn:#e5b563; --warn-soft:#332a19;
      --critical:#e2857c; --critical-soft:#3a2320;
    }
  }
  :root[data-theme="dark"]{
    --paper:#15181a; --surface:#1d2124; --ink:#e9ece8; --ink-soft:#a3ac9f; --line:#33383a;
    --consult:#8fa3d6; --consult-soft:#232a3c; --rapport:#d998a9; --rapport-soft:#332529;
    --ok:#5cc491; --ok-soft:#1c2e26; --warn:#e5b563; --warn-soft:#332a19;
    --critical:#e2857c; --critical-soft:#3a2320;
  }
  :root[data-theme="light"]{
    --paper:#eef1ec; --surface:#ffffff; --ink:#1d2420; --ink-soft:#586158; --line:#d9ded7;
    --consult:#2c3e6b; --consult-soft:#e7eaf3; --rapport:#8b4a5f; --rapport-soft:#f3e6ea;
    --ok:#2f855a; --ok-soft:#e4f2ea; --warn:#b7791f; --warn-soft:#faf1de;
    --critical:#c0392b; --critical-soft:#fbe7e4;
  }
  *{box-sizing:border-box;}
  html,body{margin:0;padding:0;}
  body{
    background:var(--paper); color:var(--ink);
    font-family:"Yu Gothic","YuGothic","Hiragino Sans","Noto Sans JP",-apple-system,sans-serif;
    line-height:1.6; -webkit-text-size-adjust:100%; min-height:100vh;
  }
  .page{ max-width:640px; margin:0 auto; padding:20px 16px 56px; display:flex; flex-direction:column; gap:18px; }
  .masthead{ display:flex; flex-direction:column; gap:10px; }
  .masthead h1{
    font-family:"Yu Mincho","YuMincho","Hiragino Mincho ProN",serif;
    font-size:1.5rem; font-weight:600; letter-spacing:.04em; margin:0; text-wrap:balance;
  }
  .masthead .date{ font-size:.82rem; color:var(--ink-soft); font-variant-numeric:tabular-nums; }
  .banner{ display:flex; align-items:center; gap:10px; padding:12px 14px; border-radius:10px; font-size:.92rem; font-weight:600; }
  .banner.attn{ background:var(--warn-soft); color:var(--warn); }
  .banner.calm{ background:var(--ok-soft); color:var(--ok); }
  .banner .dot{ width:9px;height:9px;border-radius:50%; background:currentColor; flex:none; }
  .card{ background:var(--surface); border:1px solid var(--line); border-radius:14px; overflow:hidden; }
  .card-head{ display:flex; align-items:baseline; justify-content:space-between; gap:10px; padding:16px 18px 12px; border-left:4px solid var(--accent); }
  .card-head h2{
    font-family:"Yu Mincho","YuMincho","Hiragino Mincho ProN",serif;
    font-size:1.15rem; font-weight:600; margin:0; color:var(--accent); letter-spacing:.02em;
  }
  .card-head .updated{ font-size:.72rem; color:var(--ink-soft); white-space:nowrap; font-variant-numeric:tabular-nums; }
  .card-body{ padding:0 18px 18px; border-left:4px solid var(--accent); display:flex; flex-direction:column; gap:16px; }
  .section-label{ font-size:.7rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase; color:var(--ink-soft); margin:0 0 8px; }
  .todos{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px; }
  .todo{ display:flex; gap:10px; align-items:flex-start; padding:10px 12px; border-radius:9px; background:var(--paper); font-size:.9rem; }
  .todo.flag{ background:var(--warn-soft); }
  .todo .mark{ flex:none; width:20px;height:20px; border-radius:50%; display:flex;align-items:center;justify-content:center; font-size:.68rem; font-weight:700; margin-top:1px; }
  .todo .mark.plain{ background:var(--consult-soft); color:var(--accent); }
  .todo.flag .mark{ background:var(--warn); color:var(--surface); }
  .todo .txt b{ font-weight:600; }
  .todo .txt span{ display:block; color:var(--ink-soft); font-size:.82rem; margin-top:2px; }
  .chips{ display:flex; flex-wrap:wrap; gap:7px; }
  .chip{ display:inline-flex; align-items:center; gap:6px; padding:5px 10px 5px 8px; border-radius:999px; font-size:.78rem; font-weight:600; white-space:nowrap; }
  .chip .dot{ width:7px;height:7px;border-radius:50%; flex:none; }
  .chip.ok{ background:var(--ok-soft); color:var(--ok); }
  .chip.ng{ background:var(--critical-soft); color:var(--critical); }
  .metrics{ display:flex; gap:10px; }
  .metric{ flex:1; background:var(--paper); border-radius:10px; padding:12px 14px; }
  .metric .num{ font-size:1.5rem; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.1; }
  .metric .cap{ font-size:.72rem; color:var(--ink-soft); margin-top:3px; }
  footer.note{ text-align:center; font-size:.76rem; color:var(--ink-soft); padding-top:4px; }
"""


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def render_todos(todos: list) -> str:
    if not todos:
        return '<li class="todo"><span class="mark plain">–</span><span class="txt">特にありません</span></li>'
    out = []
    for i, t in enumerate(todos, 1):
        flag = t.get("flag")
        title = esc(t.get("title", "")).lstrip("⚠️🚨 ").strip()
        detail = esc(t.get("detail", ""))
        cls = "todo flag" if flag else "todo"
        mark = '<span class="mark">!</span>' if flag else f'<span class="mark plain">{i}</span>'
        out.append(f'<li class="{cls}">{mark}<span class="txt"><b>{title}</b><span>{detail}</span></span></li>')
    return "\n".join(out)


def render_chips(checks: list) -> str:
    out = []
    for c in checks:
        ok = c.get("ok")
        cls = "chip ok" if ok else "chip ng"
        out.append(f'<span class="{cls}"><span class="dot"></span>{esc(c.get("label", ""))}</span>')
    return "\n".join(out)


def render_metrics(metrics: list) -> str:
    out = []
    for m in metrics:
        val = esc(m.get("value", ""))
        unit = esc(m.get("unit", ""))
        cap = esc(m.get("caption", ""))
        out.append(
            f'<div class="metric"><div class="num">{val}'
            f'<span style="font-size:.85rem;font-weight:600;">{unit}</span></div>'
            f'<div class="cap">{cap}</div></div>'
        )
    return "\n".join(out)


def render_account_card(snap: dict) -> str:
    account = snap.get("account", "")
    accent, _soft = ACCENT.get(account, ("var(--consult)", "var(--consult-soft)"))
    updated = esc(snap.get("updated", ""))
    return f"""
  <section class="card" style="--accent:{accent}">
    <div class="card-head">
      <h2>{esc(account)}</h2>
      <div class="updated">{updated.split(" ")[-1] if " " in updated else updated}更新</div>
    </div>
    <div class="card-body">
      <div>
        <p class="section-label">今日やること</p>
        <ul class="todos">
{render_todos(snap.get("todos", []))}
        </ul>
      </div>
      <div>
        <p class="section-label">自動化の状態</p>
        <div class="chips">
{render_chips(snap.get("checks", []))}
        </div>
      </div>
      <div class="metrics">
{render_metrics(snap.get("metrics", []))}
      </div>
    </div>
  </section>"""


def build(snapshots: list) -> str:
    n_flagged_accounts = []
    for snap in snapshots:
        if any(t.get("flag") for t in snap.get("todos", [])) or any(not c.get("ok") for c in snap.get("checks", [])):
            n_flagged_accounts.append(snap.get("account", ""))

    if n_flagged_accounts:
        banner = f'<div class="banner attn"><span class="dot"></span>{"・".join(n_flagged_accounts)}に対応が必要な項目があります</div>'
    else:
        banner = '<div class="banner calm"><span class="dot"></span>すべて順調です</div>'

    latest_updated = max((s.get("updated", "") for s in snapshots), default="")
    cards = "\n".join(render_account_card(s) for s in snapshots)

    return f"""<title>運用司令室</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>

<div class="page">
  <div class="masthead">
    <h1>運用司令室</h1>
    <div class="date">{esc(latest_updated)} 時点</div>
    {banner}
  </div>
{cards}
  <footer class="note">毎朝更新されます（コンサル垢 5:00・ラポール垢 6:45）</footer>
</div>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshots", nargs="+", help="status_snapshot.json のパス（複数可）")
    ap.add_argument("-o", "--output", default="status_page.html")
    args = ap.parse_args()

    snaps = []
    for p in args.snapshots:
        snaps.append(json.loads(Path(p).read_text(encoding="utf-8")))

    html = build(snaps)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"生成完了: {args.output}")


if __name__ == "__main__":
    main()
