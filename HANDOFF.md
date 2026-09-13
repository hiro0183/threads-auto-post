# HANDOFF.md — threads_tool（コンサル垢）の現在地カード

> **これは「次にこのrepoを触る人（別セッションのClaude／Codex／Mac／未来の自分）」への引き継ぎ書。**
> 全案件の日記は Obsidian `⭐_現在の作業状況.md`、このrepo 1つの現在地はここ。**触ったら終わりに必ずここを更新する**（上書きでよい・日付を変える）。
> 最終更新: **2026-09-13（日）** ／ 更新者: Claude Fable 5.1（Win）

---

## 1. いま何をしている案件か

**フォロワー最大化 × 対面サポート（無料の経営の問診）増** の全施策を組み、実装まで進めた（2026-09-13）。
- 正本: `docs/2026-09-13_フォロワー最大化×面談増_全施策.md`（Obsidian `コンサルThreads/⭐フォロワー最大化×面談増_全施策_2026-09-13.md` は写し）
- 合言葉: `コンサル垢の伸ばし方の続き`
- 結論: 真因は投稿の質ではなく **「見られる→フォロー→会話→問診」の変換が空**（300万views→900人=0.03%）。本数は減らさず役割を組み替える。Codex GPT-5.5 の独立診断も一致

## 2. 動いているもの（触る前に知っておく）

| 何が | どこで | いつ | 状態 |
|:--|:--|:--|:--|
| 週次企画（フック168本） | claude.ai ルーティン（Sonnet） | 日曜 04:06 JST | 稼働中。手順の正本 `prompts/weekly_plan_routine.md` |
| 日次執筆（本文・3日先まで） | claude.ai ルーティン（Sonnet） | 毎日 06:00 JST | 稼働中。正本 `prompts/daily_writing_routine.md`／`CLAUDE.md` |
| 検品 | claude.ai ルーティン（Haiku） | 毎日 12:00 JST | 稼働中 |
| 投稿 | Render `scheduler.py` → `post_runner.py` | `SLOT_PLAN` の24枠（06:00〜22:00） | 稼働中。到達率 9/06〜9/12 は7日とも100% |
| 到達率・実測の取り込み | GitHub Actions `ingest_render.yml` | 毎日 06:20 JST | 稼働中 |
| 絡み候補の検索（新設） | GitHub Actions `engage_candidates.yml` | 毎日 06:40 JST | **未push・権限未取得のため候補0件で正常終了する設計** |
| トークン更新 | GitHub Actions `refresh_token.yml` | 毎月1日 | 稼働中。現トークン期限 2026-10-30 |

## 3. 未push・途中のもの（ここが一番大事）

**ローカル master は origin より 2コミット先行・未push（2026-09-13 22:00時点）**

| コミット | 中身 | pushすると何が起きるか |
|:--|:--|:--|
| `1b7af90` | 絡み部門（`engage_list.py`・`prompts/engage_rules.md`・`engage/`・workflow）／`threads_auth.py` SCOPES+2／`threads_api.py` keyword_search等／**`post_runner.py` にトピックタグ** | **Renderが再デプロイされ、以後のroot投稿に `整体院経営` のトピックタグが付く**（失敗時はタグ無しで再試行するので投稿は止まらない）。workflowは権限取得まで何もしない |
| `5230a87` | `docs/…全施策.md`／`prompts/pinned_post.md`（固定ポスト3案・bio v3・症状別CTA7本・告知・DM文＝**提案・未承認**）／`assets/lead_magnet/`（棚卸しシート）／`weekly_report.py`・`ops_dashboard.py` のLINE記入先を `state/line_inflow_manual.jsonl` へ | クラウドの週次企画が `state/line_inflow_manual.jsonl` を読めるようになる。投稿には影響なし |

- **push はなりあいさんの判断待ち**（トピックタグが本番に効くため）。OKが出たら `git -c credential.helper= push https://<user>:<token>@github.com/hiro0183/threads-auto-post.git master:master`（Bashからの素の `git push` はGCMのダイアログが出せず止まる）
- 未コミット（残してよい）: `engage/2026-09-13.md`（デモ出力・架空候補と明記）／`posts/2026-09-13.json.bak_*`／`prompts/stories.md.bak_20260912`
- **実験台帳** `experiments/ledger.json` の W35-01〜03 は judge_on **2026-09-21**。02・03は baseline 無効。閉じるのは人間。次に開く3枚の案は `docs/…全施策.md` §5

## 4. ⏸ なりあいさん待ち（本人にしかできない・この順で）

1. **Meta for Developers で `threads_keyword_search`・`threads_profile_discovery` を有効化 → `python threads_auth.py` → `python token_manager.py --seed` → GitHub secret `THREADS_ACCESS_TOKEN`・Render環境変数を新トークンに**（これで `engage_list.py` が毎朝「絡みリスト」を出せる）
2. 固定ポストを1本選んで投稿・固定（`prompts/pinned_post.md` 案A推奨。投稿日の22:00はCTA無しにする）
3. bio v3 に差し替え（「院長・社長へ」を残すか「院長へ」に絞るかは本人判断）
4. UTAGE で mtid=`uVqmOIrsLg8j` の週間LINE登録数を教える → `state/line_inflow_manual.jsonl` に記入（Claudeが代筆可）
5. 棚卸しシートの置き場を決める（UTAGE配布ページ／公開ページ／DMでPDF直送）→ URLを告知文・DM文へ
6. 未push 2件のpush可否／A4「会話5枠→2枠」の承認
7. （権限取得後）毎朝10分、`engage/YYYY-MM-DD.md` の5件に返信。**送信は必ず人間**

## 5. 次にAIがやること（承認が出たら）

- 採用された固定ポスト案を `prompts/profile.md` に正本化
- 症状別CTAを `prompts/funnel_rules.md` と `weekly_plan_routine.md` に組み込み（22:00は症状1〜7を輪番・`theme` に `CTA:症状N`）
- 棚卸しシート告知を週1本（曜日固定）で企画へ。その日の22:00はCTA無し
- 9/21に台帳3枚を閉じてから W39-01〜03（固定ポスト＋bio／絡み／トピックタグ）を開く
- Chrome拡張が繋がったら、コンサル垢でログイン中のときだけThreads検索で競合調査（未実施）

## 6. 罠（知らないと壊す）

- **`reports/` はgit管理外**（`.gitignore`）。クラウドに読ませる正本は `docs/` か `prompts/` に置く
- **時刻の変更は `SLOT_PLAN` だけを編集**（`POST_SCHEDULE` は導出。7/30に片側だけ変えて22日間投稿が欠けた）
- **CTAは1日1本**（22:00のみ・2026-09-11決定）。`taboo.md`・`CLAUDE.md`・`post_runner.py` MAX_CTA_PER_DAY を同時に直す
- **数字は `persona.md` の確認済み実数のみ**。8,500円／1,500円／250万→100万／保険の話は禁止。450万・500万・850万は事実でも出さない（「300を切ったことがない」と書く）。**数字を禁止するときは persona.md・stories.md・CLAUDE.md・hook_rules.md の4つ同時**
- `check_hooks.py`（週次プラン）と `check_body_style.py`（本文）は必ず終了コード0まで直す。**検品の単発NGを鵜呑みに本文を書き換えるループは禁止**
- **@rapport.diet（ダイエット垢）には閲覧を含め一切触らない。** このrepoはコンサル垢専用。`threads_tool_rapport`（産後垢）と混同しない
- クラウドルーティンにOneDrive／ローカルパスを書いても届かない（`state/` や `prompts/` に置く）
- 手元で直しても **pushして初めてクラウドのルールが変わる**（8/21〜9/1に10日間届かなかった実例）
- 司令室の赤は「古い検品結果」「PCスリープ明けの追いかけ実行」のことがある。まず `reach_status.json`（実物）を見る
- **Codexに触らせない場所:** Render・クラウド定期便・`post_runner.py`／`scheduler.py` の投稿経路・トークン。Codexは読み取り・分析・提案・レビューまで（今回もそう使った）

## 7. 主要ファイルの地図

| 目的 | ファイル |
|:--|:--|
| 日次執筆のルールブック | `CLAUDE.md` |
| 数字の棚／場面の棚／禁じ手 | `prompts/persona.md`／`prompts/stories.md`／`prompts/taboo.md` |
| フック・本文・検品・4層 | `prompts/hook_rules.md`／`body_rules.md`／`gate.md`／`funnel_rules.md` |
| プロフィール正本／固定ポスト提案 | `prompts/profile.md`／`prompts/pinned_post.md` |
| 絡み部門 | `engage_list.py`／`engage/README.md`／`prompts/engage_rules.md`／`state/engaged.json` |
| リードマグネット | `assets/lead_magnet/tanaoroshi_sheet.html`・`.pdf` |
| 実測・レポート | `weekly_report.py`／`reach_check.py`／`collect_insights.py`／`collect_replies.py`／`experiments/ledger.json` |
| 導線の計測（手動記入） | `state/line_inflow_manual.jsonl` |
| 投稿の配管 | `post_runner.py`（SLOT_PLAN）／`scheduler.py`／`render.yaml` |

## 8. 記録の場所（Obsidian）

- 作業ログ: `コンサルThreads/作業ログ/2026-09-13_フォロワー最大化と面談増の全施策_絡み部門新設.md`
- セッションまとめ: `🧭_行動記録/セッションまとめ/2026-09-13_Win_Claude_コンサル垢_フォロワー最大化と面談増の全施策.md`
- 案件一覧: `📋_案件一覧_続きはどれ.md`（`コンサル垢の伸ばし方の続き` の行）
- スマホ用まとめ: https://claude.ai/code/artifact/ad1e4909-9d2f-45fa-a28c-29603b74e252
