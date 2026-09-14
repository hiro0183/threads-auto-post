"""絡み部門（2026-09-13新設）: 他アカウントへの返信下書きを毎朝作る。

背景:
  フォロワー911人で2ヶ月横ばい・実質エンゲージ率0.07%・読者返信ほぼゼロ。
  全投稿が自動化され、人間が一度も他アカウントに絡んでいない。「絡み」が唯一未着手の
  成長レバーで、本人が1日10分でできる形にするのがこのスクリプト。

使い方:
  python engage_list.py                 # 検索→候補→返信下書き→ engage/YYYY-MM-DD.md
  python engage_list.py --search-only   # 検索と候補選定だけ（AI不使用）→ engage/candidates/YYYY-MM-DD.json
  python engage_list.py --draft-only    # 既存の candidates から下書きだけ
  python engage_list.py --demo          # scope未取得でも動作確認できるデモ（架空サンプル5件）
  python engage_list.py --done ID1 ID2  # 返信し終えた投稿IDを state/engaged.json に記録

注意:
  ・threads_keyword_search / threads_profile_discovery のscopeが無い間、keyword_searchは
    500を返す（threads_api.ThreadsAPI.keyword_search が例外を握って空リストを返す設計）。
    その場合このスクリプトは「候補0件」でエラーにせず正常終了する。
  ・返信の送信は必ず人間が行う。このスクリプトは絶対に返信を自動投稿しない。
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).resolve().parent
ENGAGE_DIR = BASE / "engage"
CANDIDATES_DIR = ENGAGE_DIR / "candidates"
STATE_DIR = BASE / "state"
ENGAGED_PATH = STATE_DIR / "engaged.json"
REPLIES_PATH = BASE / "replies_collected.jsonl"
KEYWORDS_PATH = ENGAGE_DIR / "keywords.txt"
DEMO_PATH = ENGAGE_DIR / "demo_candidates.json"

SELF_USERNAME = "hiro_nariai_salon_"
PROMO_WORDS = ["LINE登録", "公式LINE", "DMください", "募集", "限定"]
URL_RE = re.compile(r"https?://")
RELEVANCE_WORDS = [
    "院長", "整体", "治療院", "サロン", "経営", "患者", "予約",
    "単価", "リピート", "スタッフ", "売上", "時間",
]
MIN_TEXT_LEN = 20
FRESH_HOURS = 72
TOP_N = 8


# ── 検索（実データ） ──────────────────────────────────────

def load_keywords() -> list[str]:
    if not KEYWORDS_PATH.exists():
        return []
    out = []
    for line in KEYWORDS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def get_access_token() -> str | None:
    """tokens.json（ローカルの再認証結果）を優先し、無ければ THREADS_ACCESS_TOKEN（CIのsecret）を使う。
    2026-09-14: .env の古い種トークンが tokens.json より優先されて検索が500になった実例があるため順序を入れ替えた。
    OAuthフローは絶対に起動しない（CIでハングするため）。"""
    try:
        from threads_auth import load_tokens
        tokens = load_tokens()
    except Exception:
        tokens = None
    if tokens and tokens.get("access_token"):
        return tokens.get("access_token")
    return os.environ.get("THREADS_ACCESS_TOKEN") or None


def get_api():
    """threads_api.ThreadsAPI をOAuthフローなしで組み立てる。トークンが無ければNone。"""
    token = get_access_token()
    if not token:
        return None
    from threads_api import ThreadsAPI
    api = ThreadsAPI.__new__(ThreadsAPI)
    api.access_token = token
    api.user_id = None
    return api


def search_candidates_live() -> list[dict]:
    """keywords.txt の各語をTOP/RECENT両方で検索する。scope未取得や失敗時は空リスト。"""
    api = get_api()
    if not api:
        print("[INFO] トークンが見つかりません（候補0件）", file=sys.stderr)
        return []

    keywords = load_keywords()
    if not keywords:
        print("[WARN] engage/keywords.txt が空です", file=sys.stderr)
        return []

    raw = []
    seen_ids = set()
    for kw in keywords:
        for search_type in ("TOP", "RECENT"):
            results = api.keyword_search(kw, search_type=search_type, limit=25)
            for r in results:
                rid = r.get("id")
                if not rid or rid in seen_ids:
                    continue
                seen_ids.add(rid)
                r = dict(r)
                r["_keyword"] = kw
                r["_search_type"] = search_type
                raw.append(r)
    return raw


# ── フィルタ・スコア ──────────────────────────────────────

def is_promotional(text: str) -> bool:
    text = text or ""
    if URL_RE.search(text):
        return True
    return any(w in text for w in PROMO_WORDS)


def parse_timestamp(ts: str):
    """Threads APIの "+0000" 形式タイムゾーンをfromisoformatが読めるよう正規化する。"""
    if not ts:
        return None
    t = ts.strip()
    m = re.match(r"^(.*)([+-]\d{2})(\d{2})$", t)
    if m and ":" not in t[-6:]:
        t = f"{m.group(1)}{m.group(2)}:{m.group(3)}"
    try:
        dt = datetime.fromisoformat(t)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def hours_ago(dt: datetime) -> float:
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 3600


def score_candidate(c: dict, hours: float) -> float:
    text = c.get("text") or ""
    like = c.get("like_count", 0) or 0
    reply = c.get("reply_count", 0) or 0
    recency = max(0.0, (FRESH_HOURS - hours) / FRESH_HOURS * 10)
    relevance = sum(text.count(w) for w in RELEVANCE_WORDS) * 2
    return like * 2 + reply * 3 + recency + relevance


def filter_candidates(raw: list[dict], engaged_ids: set) -> list[dict]:
    filtered = []
    for c in raw:
        cid = c.get("id")
        if not cid or cid in engaged_ids:
            continue
        username = c.get("username") or ""
        if username == SELF_USERNAME:
            continue
        text = c.get("text") or ""
        if len(text) < MIN_TEXT_LEN:
            continue
        if is_promotional(text):
            continue
        dt = parse_timestamp(c.get("timestamp", ""))
        if not dt:
            continue
        h = hours_ago(dt)
        if h < 0 or h > FRESH_HOURS:
            continue
        c = dict(c)
        c["_hours_ago"] = h
        c["_score"] = score_candidate(c, h)
        filtered.append(c)

    # 同一usernameは1日1件まで（最高スコアだけ残す）
    best_by_user = {}
    for c in filtered:
        u = c.get("username")
        if u not in best_by_user or c["_score"] > best_by_user[u]["_score"]:
            best_by_user[u] = c
    result = list(best_by_user.values())
    result.sort(key=lambda x: -x["_score"])
    return result


# ── state/engaged.json（済み管理） ─────────────────────────

def load_engaged() -> dict:
    if not ENGAGED_PATH.exists():
        return {}
    try:
        return json.loads(ENGAGED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_engaged(d: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ENGAGED_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_done(ids: list[str]):
    engaged = load_engaged()
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).isoformat()
    for i in ids:
        engaged[i] = {"date": now}
    save_engaged(engaged)
    print(f"{len(ids)}件を state/engaged.json に記録しました: {', '.join(ids)}")


# ── candidates ファイル ────────────────────────────────────

def get_today_jst() -> str:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")


def candidates_path(date_str: str) -> Path:
    return CANDIDATES_DIR / f"{date_str}.json"


def save_candidates(date_str: str, candidates: list[dict]):
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    candidates_path(date_str).write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_candidates(date_str: str):
    p = candidates_path(date_str)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── 読者返信（まず返す） ────────────────────────────────────

def load_priority_replies(engaged_ids: set, days: int = 7) -> list[dict]:
    if not REPLIES_PATH.exists():
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = []
    for line in REPLIES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("id") in engaged_ids:
            continue
        post_date = d.get("post_date") or (d.get("timestamp") or "")[:10]
        if post_date and post_date < cutoff:
            continue
        rows.append(d)
    return rows


# ── AI下書き ───────────────────────────────────────────────

def extract_section(full_text: str, start_marker: str) -> str:
    """指定した "## " 見出しから、次の同レベル見出しの直前までを抜き出す"""
    lines = full_text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == start_marker:
            start_idx = i
            break
    if start_idx is None:
        return ""
    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        if lines[j].startswith("## ") and lines[j].strip() != start_marker:
            end_idx = j
            break
    return "\n".join(lines[start_idx:end_idx])


def build_ai_prompt(candidates: list[dict], priority_replies: list[dict]) -> str:
    engage_rules = (BASE / "prompts" / "engage_rules.md").read_text(encoding="utf-8")
    persona_full = (BASE / "prompts" / "persona.md").read_text(encoding="utf-8")
    persona_section = extract_section(persona_full, "## 発信者=ヒロ先生")
    stories_full = (BASE / "prompts" / "stories.md").read_text(encoding="utf-8")
    stories_section = extract_section(stories_full, "## B. 言葉の棚（実際に口にされた言葉だけ）")

    lines = [
        "# 絡み部門: 返信下書き作成",
        "",
        "以下のルールと素材を厳密に守り、指定した投稿への返信下書きをJSON形式で出力してください。",
        "出力はJSONのみ。説明文・前置き・コードフェンスは付けないでください。",
        "",
        "## ルール（prompts/engage_rules.md）",
        engage_rules,
        "",
        "## 発信者の実数（persona.md抜粋・これ以外の数字は使わない）",
        persona_section,
        "",
        "## 言葉の棚（stories.md抜粋・実際に口にされた言葉だけ）",
        stories_section,
    ]

    if priority_replies:
        lines.append("")
        lines.append("## まず返す対象: 自分の投稿への読者返信（最優先・当日中に返す）")
        for r in priority_replies:
            lines.append(f"- id={r.get('id')} @{r.get('username')}: {r.get('text')}")

    lines.append("")
    lines.append("## 今日の絡み候補（上位8件）")
    for c in candidates:
        lines.append(
            f"- id={c.get('id')} @{c.get('username')} "
            f"いいね{c.get('like_count', 0)}・返信{c.get('reply_count', 0)}: {c.get('text')}"
        )

    lines.append("")
    lines.append("## 出力フォーマット（JSONのみ・このキー名を厳守）")
    lines.append("""{
  "priority_replies": [{"id": "元のid", "draft": "80字以内の返信下書き"}],
  "candidates": [{"id": "元のid", "A": "共感+自分の具体案(80字以内)", "B": "質問で返す案(80字以内)"}]
}""")
    return "\n".join(lines)


def try_parse_json(text: str):
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n", "", t)
        t = re.sub(r"\n```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(t[start:end + 1])
        except Exception:
            return None
    return None


def generate_drafts(candidates: list[dict], priority_replies: list[dict]):
    """AIを1回だけ呼んで下書きを作る。JSON解析に失敗したら (None, 生テキスト) を返す。"""
    if not candidates and not priority_replies:
        return {"priority_replies": [], "candidates": []}, None

    from content_generator import claude_headless

    prompt = build_ai_prompt(candidates, priority_replies)
    try:
        raw = claude_headless(prompt, model="sonnet", timeout=300)
    except Exception as e:
        print(f"[WARN] AI呼び出し失敗: {e}", file=sys.stderr)
        return None, f"(AI呼び出し失敗: {e})"

    parsed = try_parse_json(raw)
    if parsed is None:
        return None, raw
    return parsed, None


# ── Markdown出力 ────────────────────────────────────────────

def format_hours_ago(h: float) -> str:
    if h < 1:
        return f"{max(1, int(h * 60))}分前"
    return f"{int(h)}時間前"


def build_markdown(date_str, candidates, priority_replies, drafts, raw_fallback, demo=False) -> str:
    lookup_c, lookup_p = {}, {}
    if drafts:
        for d in drafts.get("candidates", []) or []:
            lookup_c[d.get("id")] = d
        for d in drafts.get("priority_replies", []) or []:
            lookup_p[d.get("id")] = d

    lines = []
    if demo:
        lines.append("⚠️ デモ（架空の候補）")
        lines.append("")
    lines.append(f"# 絡みリスト {date_str}（所要10分・5件でOK）")
    lines.append("")

    lines.append("## 0. まず返す（自分の投稿への読者返信）")
    if not priority_replies:
        lines.append("（対象なし）")
    else:
        for r in priority_replies:
            d = lookup_p.get(r.get("id"), {})
            draft_text = d.get("draft") if isinstance(d, dict) else None
            if not draft_text:
                draft_text = "(下書きなし・下のAI生テキストを参照)" if raw_fallback else "(下書きなし)"
            text = (r.get("text") or "")[:80]
            lines.append(f"- [{r.get('permalink', '')}] @{r.get('username')}「{text}」 → 下書き: {draft_text}")
    lines.append("")

    lines.append("## 1. 今日の候補（上から順に・5件やれば十分）")
    if not candidates:
        lines.append("（対象なし）")
    else:
        for i, c in enumerate(candidates, 1):
            d = lookup_c.get(c.get("id"), {})
            a = d.get("A") if isinstance(d, dict) else None
            b = d.get("B") if isinstance(d, dict) else None
            if not a:
                a = "(下書きなし・下のAI生テキストを参照)" if raw_fallback else "(下書きなし)"
            if not b:
                b = "(下書きなし・下のAI生テキストを参照)" if raw_fallback else "(下書きなし)"
            ago = format_hours_ago(c.get("_hours_ago", 0))
            lines.append(f"### {i}) @{c.get('username')}（いいね{c.get('like_count', 0)}・返信{c.get('reply_count', 0)}・{ago}）")
            lines.append(f"> {(c.get('text') or '')[:120]}")
            lines.append(f"🔗 {c.get('permalink', '')}")
            lines.append(f"A: {a}")
            lines.append(f"B: {b}")
            lines.append("")

    lines.append("## 2. 終わったら")
    lines.append("`python engage_list.py --done ID1 ID2`（または翌日自動で72時間過ぎて消える）")

    if raw_fallback:
        lines.append("")
        lines.append("---")
        lines.append("⚠️ AIの出力がJSONとして解析できなかったため、生成された文章をそのまま貼り付けます。")
        lines.append("```")
        lines.append(raw_fallback)
        lines.append("```")

    return "\n".join(lines) + "\n"


def write_output_md(date_str, candidates, priority_replies, drafts, raw_fallback, demo=False):
    ENGAGE_DIR.mkdir(parents=True, exist_ok=True)
    md = build_markdown(date_str, candidates, priority_replies, drafts, raw_fallback, demo=demo)
    out_path = ENGAGE_DIR / f"{date_str}.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


# ── モード ──────────────────────────────────────────────────

def run_search_only():
    date_str = get_today_jst()
    engaged = load_engaged()
    raw = search_candidates_live()
    filtered = filter_candidates(raw, set(engaged.keys()))
    top = filtered[:TOP_N]
    if not top:
        print("候補0件（scope未取得 or 該当なしのため、正常終了）")
        return
    save_candidates(date_str, top)
    print(f"候補{len(top)}件を engage/candidates/{date_str}.json に保存しました")


def run_draft_only():
    date_str = get_today_jst()
    candidates = load_candidates(date_str) or []
    if not candidates and not candidates_path(date_str).exists():
        print(f"engage/candidates/{date_str}.json が見つかりません。先に --search-only を実行してください")
    engaged = load_engaged()
    priority = load_priority_replies(set(engaged.keys()))
    drafts, raw_fallback = generate_drafts(candidates, priority)
    out_path = write_output_md(date_str, candidates, priority, drafts, raw_fallback)
    print(f"{out_path} を作成しました（候補{len(candidates)}件・まず返す{len(priority)}件）")


def run_full():
    date_str = get_today_jst()
    engaged = load_engaged()
    raw = search_candidates_live()
    filtered = filter_candidates(raw, set(engaged.keys()))
    top = filtered[:TOP_N]
    if top:
        save_candidates(date_str, top)
    priority = load_priority_replies(set(engaged.keys()))
    drafts, raw_fallback = generate_drafts(top, priority)
    out_path = write_output_md(date_str, top, priority, drafts, raw_fallback)
    print(f"{out_path} を作成しました（候補{len(top)}件・まず返す{len(priority)}件）")


def run_demo():
    date_str = get_today_jst()
    if not DEMO_PATH.exists():
        print(f"engage/demo_candidates.json がありません")
        return
    candidates = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    now_dt = datetime.now(timezone.utc)
    for c in candidates:
        dt = parse_timestamp(c.get("timestamp", ""))
        c["_hours_ago"] = hours_ago(dt) if dt else 5.0
        c["_score"] = score_candidate(c, c["_hours_ago"])

    engaged = load_engaged()
    priority = load_priority_replies(set(engaged.keys()))
    drafts, raw_fallback = generate_drafts(candidates, priority)
    out_path = write_output_md(date_str, candidates, priority, drafts, raw_fallback, demo=True)
    print(f"[DEMO] {out_path} を作成しました（架空の候補{len(candidates)}件・まず返す{len(priority)}件）")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = sys.argv[1:]

    if "--done" in args:
        idx = args.index("--done")
        ids = [a for a in args[idx + 1:] if not a.startswith("--")]
        if not ids:
            print("IDを指定してください: python engage_list.py --done ID1 ID2")
            return
        mark_done(ids)
        return

    if "--demo" in args:
        run_demo()
        return

    if "--search-only" in args:
        run_search_only()
        return

    if "--draft-only" in args:
        run_draft_only()
        return

    run_full()


if __name__ == "__main__":
    main()
