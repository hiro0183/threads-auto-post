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
from datetime import datetime, timedelta, timezone
from pathlib import Path

ACCENT = {
    "コンサル垢": ("var(--consult)", "var(--consult-soft)"),
    "ラポール垢": ("var(--rapport)", "var(--rapport-soft)"),
}

FONT_LINK = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Zen+Maru+Gothic:wght@500;700&display=swap">'

CSS = """
  :root{
    --paper:#fff3d6; --paper-dot:#f5c400; --surface:#ffffff; --ink:#241832; --ink-soft:#7a6f8c; --line:#e7d9a8;
    --consult:#5b3a8e; --consult-soft:#ece3fa; --rapport:#1f9e64; --rapport-soft:#e1f6ea;
    --ok:#1f9e64; --ok-soft:#e1f6ea; --warn:#e08a00; --warn-soft:#fff0d6;
    --critical:#e63950; --critical-soft:#fde3e6;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --paper:#1c1530; --paper-dot:#2c2148; --surface:#251c3d; --ink:#f3ecff; --ink-soft:#b8a9d6; --line:#3d3160;
      --consult:#b79bf0; --consult-soft:#332a55; --rapport:#7be3ac; --rapport-soft:#1f3d2c;
      --ok:#7be3ac; --ok-soft:#1f3d2c; --warn:#ffc266; --warn-soft:#3d3016;
      --critical:#ff8a9b; --critical-soft:#452230;
    }
  }
  :root[data-theme="dark"]{
    --paper:#1c1530; --paper-dot:#2c2148; --surface:#251c3d; --ink:#f3ecff; --ink-soft:#b8a9d6; --line:#3d3160;
    --consult:#b79bf0; --consult-soft:#332a55; --rapport:#7be3ac; --rapport-soft:#1f3d2c;
    --ok:#7be3ac; --ok-soft:#1f3d2c; --warn:#ffc266; --warn-soft:#3d3016;
    --critical:#ff8a9b; --critical-soft:#452230;
  }
  :root[data-theme="light"]{
    --paper:#fff3d6; --paper-dot:#f5c400; --surface:#ffffff; --ink:#241832; --ink-soft:#7a6f8c; --line:#e7d9a8;
    --consult:#5b3a8e; --consult-soft:#ece3fa; --rapport:#1f9e64; --rapport-soft:#e1f6ea;
    --ok:#1f9e64; --ok-soft:#e1f6ea; --warn:#e08a00; --warn-soft:#fff0d6;
    --critical:#e63950; --critical-soft:#fde3e6;
  }
  *{box-sizing:border-box;}
  html,body{margin:0;padding:0;}
  body{
    background-color:var(--paper);
    background-image:radial-gradient(var(--paper-dot) 1.2px, transparent 1.2px);
    background-size:14px 14px;
    color:var(--ink);
    font-family:"Zen Maru Gothic","Hiragino Maru Gothic Pro","Yu Gothic",sans-serif;
    line-height:1.6; -webkit-text-size-adjust:100%; min-height:100vh;
  }
  .page{ max-width:640px; margin:0 auto; padding:20px 16px 56px; display:flex; flex-direction:column; gap:18px; }
  .masthead{ display:flex; flex-direction:column; gap:10px; }
  .masthead h1{
    font-family:"Dela Gothic One",sans-serif;
    font-size:1.4rem; font-weight:400; letter-spacing:.02em; margin:0; text-wrap:balance;
    color:var(--consult);
  }
  .masthead .date{ font-size:.82rem; color:var(--ink-soft); font-variant-numeric:tabular-nums; font-weight:700; }
  .banner{ display:flex; align-items:center; gap:10px; padding:13px 16px; border-radius:999px; font-size:.92rem; font-weight:700;
           border:3px solid var(--ink); box-shadow:4px 4px 0 var(--ink); }
  .banner.attn{ background:var(--warn-soft); color:var(--warn); }
  .banner.calm{ background:var(--ok-soft); color:var(--ok); }
  .banner .dot{ width:9px;height:9px;border-radius:50%; background:currentColor; flex:none; }
  .card{ background:var(--surface); border:3px solid var(--ink); border-radius:20px; overflow:hidden;
         box-shadow:6px 6px 0 var(--ink); }
  .card-head{ display:flex; align-items:center; gap:12px; padding:16px 18px 12px; background:var(--accent-soft); }
  .card-head .mascot{ flex:none; }
  .card-head h2{
    font-family:"Dela Gothic One",sans-serif;
    font-size:1.05rem; font-weight:400; margin:0; color:var(--accent); letter-spacing:.01em;
  }
  .card-head .updated{ font-size:.72rem; color:var(--ink-soft); white-space:nowrap; font-variant-numeric:tabular-nums; margin-left:auto; font-weight:700; }
  .card-body{ padding:16px 18px 18px; display:flex; flex-direction:column; gap:16px; }
  .section-label{ font-size:.72rem; font-weight:700; letter-spacing:.06em; color:var(--ink-soft); margin:0 0 8px; }
  .todos{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px; }
  .todo{ display:flex; gap:10px; align-items:flex-start; padding:10px 12px; border-radius:12px; background:var(--paper); font-size:.9rem;
         border:2px solid var(--line); }
  .todo.flag{ background:var(--warn-soft); border-color:var(--warn); }
  .todo .mark{ flex:none; width:22px;height:22px; border-radius:50%; display:flex;align-items:center;justify-content:center; font-size:.7rem; font-weight:700; margin-top:1px;
               border:2px solid var(--ink); }
  .todo .mark.plain{ background:var(--consult-soft); color:var(--accent); }
  .todo.flag .mark{ background:var(--warn); color:#fff; }
  .todo .txt b{ font-weight:700; }
  .todo .txt span{ display:block; color:var(--ink-soft); font-size:.82rem; margin-top:2px; }
  .chips{ display:flex; flex-wrap:wrap; gap:7px; }
  .chip{ display:inline-flex; align-items:center; gap:6px; padding:5px 11px 5px 9px; border-radius:999px; font-size:.78rem; font-weight:700; white-space:nowrap;
         border:2px solid transparent; }
  .chip .dot{ width:7px;height:7px;border-radius:50%; flex:none; }
  .chip.ok{ background:var(--ok-soft); color:var(--ok); border-color:var(--ok); }
  .chip.ng{ background:var(--critical-soft); color:var(--critical); border-color:var(--critical); }
  .chip.unknown{ background:rgba(128,128,128,.14); color:#6b7280; border-color:rgba(128,128,128,.3); }
  .banner.stale{ background:var(--warn-soft); color:var(--warn); }
  .reachbar{ display:flex; align-items:center; gap:8px; margin-top:8px; padding:9px 14px; border-radius:12px; font-size:.82rem; font-weight:700;
             border:2px solid transparent; }
  .reachbar.ok{ background:var(--ok-soft); color:var(--ok); border-color:var(--ok); }
  .reachbar.ng{ background:var(--critical-soft); color:var(--critical); border-color:var(--critical); }
  .metrics{ display:flex; gap:10px; }
  .metric{ flex:1; background:var(--paper); border-radius:12px; padding:12px 14px; border:2px solid var(--line); }
  .metric .num{ font-size:1.4rem; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.1; font-family:"Dela Gothic One",sans-serif; }
  .metric .cap{ font-size:.72rem; color:var(--ink-soft); margin-top:3px; font-weight:700; }
  footer.note{ text-align:center; font-size:.76rem; color:var(--ink-soft); padding-top:4px; font-weight:700; }
"""


def render_mascot(accent_color: str, mood: str, size: int = 52) -> str:
    """状態に応じて表情が変わるポップなマスコット（丸っこいブロブ）。
    mood: "happy"（順調）/ "worried"（要対応）"""
    if mood == "happy":
        eyes = '<circle cx="40" cy="46" r="5" fill="#241832"/><circle cx="60" cy="46" r="5" fill="#241832"/>'
        mouth = '<path d="M40 62 Q50 71 60 62" stroke="#241832" stroke-width="4.5" fill="none" stroke-linecap="round"/>'
    else:
        eyes = ('<path d="M35 43 L45 48" stroke="#241832" stroke-width="4.5" stroke-linecap="round"/>'
                '<path d="M65 43 L55 48" stroke="#241832" stroke-width="4.5" stroke-linecap="round"/>')
        mouth = '<path d="M40 67 Q50 59 60 67" stroke="#241832" stroke-width="4.5" fill="none" stroke-linecap="round"/>'
    h = round(size * 90 / 100)
    return f"""<svg class="mascot" viewBox="0 0 100 90" width="{size}" height="{h}">
      <ellipse cx="50" cy="52" rx="42" ry="34" fill="{accent_color}" stroke="#241832" stroke-width="4"/>
      <ellipse cx="34" cy="30" rx="10" ry="7" fill="#ffffff" opacity="0.35"/>
      {eyes}
      {mouth}
    </svg>"""


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
        # ok は True / False / None（=確認できず）の3値。
        # None を False と同じ赤にすると「判定できていない」ことが「異常」として出てしまうため分ける。
        cls = "chip ok" if ok is True else ("chip ng" if ok is False else "chip unknown")
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



JST = timezone(timedelta(hours=9))
STALE_HOURS = 28  # 毎朝更新されるので、28時間を超えたら「PCが動いていない」とみなす


def _parse_updated(text: str):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text.strip(), fmt).replace(tzinfo=JST)
        except Exception:
            continue
    return None


def snapshot_age_hours(snap: dict):
    """スナップショットの古さ（時間）。判定できなければNone。

    2026-08-24追加: このページの元データ（status_snapshot.json）はなりあいさんのPCが
    毎朝作っている。PCが起動していない日は前日以前の内容がそのまま表示され、
    実際には異常が起きていても「すべて順調です」と出てしまう。
    22日間の投稿欠落を見逃した構造とまったく同じなので、古さを必ず顔に出す。
    """
    dt = _parse_updated(snap.get("updated", ""))
    if dt is None:
        return None
    return (datetime.now(JST) - dt).total_seconds() / 3600


def load_reach_status():
    """クラウド発の到達率（reach_status.json）を読む。

    PCの状態に関係なく、Renderとクラウドルーティンが毎朝更新する唯一の実測。
    スナップショットが古くても、ここだけは信用できる。
    """
    f = Path(__file__).parent / "reach_status.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


def render_reachbar() -> str:
    st = load_reach_status()
    if not st:
        return ""
    y = st.get("yesterday") or {}
    if not y:
        return ""
    rate = y.get("rate", 0)
    cls = "ok" if rate >= 100 else "ng"
    if rate >= 100:
        txt = f"投稿は出ています（{y.get('date')} {y.get('actual')}/{y.get('expected')}枠）"
    else:
        streak = st.get("miss_streak") or 0
        txt = (f"🚨 投稿が出ていません（{y.get('date')} {y.get('actual')}/{y.get('expected')}枠"
               f"・{streak}日連続）")
    return f'<div class="reachbar {cls}"><span class="dot"></span>{esc(txt)}　<span style="font-weight:500;opacity:.75">実物のThreadsを確認した結果です</span></div>'


def _age_label(snap: dict) -> str:
    updated = snap.get("updated", "")
    age = snapshot_age_hours(snap)
    short = updated.split(" ")[-1] if " " in updated else updated
    if age is not None and age > STALE_HOURS:
        return esc(f"⚠️{updated} から更新なし")
    return esc(f"{short}更新")


MASCOT_COLOR = {
    "コンサル垢": "#5B3A8E",
    "ラポール垢": "#2FA36B",
}


def render_account_card(snap: dict) -> str:
    account = snap.get("account", "")
    accent, soft = ACCENT.get(account, ("var(--consult)", "var(--consult-soft)"))
    is_ok = not (any(t.get("flag") for t in snap.get("todos", []))
                 or any(c.get("ok") is False for c in snap.get("checks", [])))
    mascot = render_mascot(MASCOT_COLOR.get(account, "#5B3A8E"), "happy" if is_ok else "worried")
    return f"""
  <section class="card" style="--accent:{accent};--accent-soft:{soft}">
    <div class="card-head">
      {mascot}
      <h2>{esc(account)}</h2>
      <div class="updated">{_age_label(snap)}</div>
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
        if any(t.get("flag") for t in snap.get("todos", [])) or any(c.get("ok") is False for c in snap.get("checks", [])):
            n_flagged_accounts.append(snap.get("account", ""))

    # 元データが古い＝PCが動いていない。中身が緑でも信用してはいけない
    stale = [s2.get("account", "") for s2 in snapshots
             if (snapshot_age_hours(s2) or 0) > STALE_HOURS]

    if stale:
        banner = ('<div class="banner stale"><span class="dot"></span>'
                  f'{"・".join(stale)}の情報が{STALE_HOURS}時間以上更新されていません'
                  '（PCが起動していない可能性。下の緑は古い情報かもしれません）</div>')
    elif n_flagged_accounts:
        banner = f'<div class="banner attn"><span class="dot"></span>{"・".join(n_flagged_accounts)}に対応が必要な項目があります</div>'
    else:
        banner = '<div class="banner calm"><span class="dot"></span>すべて順調です</div>'

    latest_updated = max((s.get("updated", "") for s in snapshots), default="")
    cards = "\n".join(render_account_card(s) for s in snapshots)

    return f"""<title>運用司令室</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
{FONT_LINK}
<style>{CSS}</style>

<div class="page">
  <div class="masthead">
    <h1>運用司令室</h1>
    <div class="date">{esc(latest_updated)} 時点</div>
    {banner}
    {render_reachbar()}
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
