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
| 絡み候補の検索（新設） | GitHub Actions `engage_candidates.yml` | 毎日 06:40 JST | push済み。**権限未取得のため候補0件で正常終了する**（再認証後に動き出す） |
| トークン更新 | GitHub Actions `refresh_token.yml` | 毎月1日 | 稼働中。現トークン期限 2026-10-30 |

## 3. 未push・途中のもの（ここが一番大事）

**✅ 2026-09-13 22:20 にpush済み（なりあいさん承認）。以後のroot投稿にトピックタグが付く。**

| コミット | 中身 | pushすると何が起きるか |
|:--|:--|:--|
| `7ca729f`（旧1b7af90） | 絡み部門（`engage_list.py`・`prompts/engage_rules.md`・`engage/`・workflow）／`threads_auth.py` SCOPES+2／`threads_api.py` keyword_search等／**`post_runner.py` にトピックタグ** | **Renderが再デプロイされ、以後のroot投稿に `整体院経営` のトピックタグが付く**（失敗時はタグ無しで再試行するので投稿は止まらない）。workflowは権限取得まで何もしない |
| `8d83416`（旧5230a87） | `docs/…全施策.md`／`prompts/pinned_post.md`（固定ポスト3案・bio v3・症状別CTA7本・告知・DM文＝**提案・未承認**）／`assets/lead_magnet/`（棚卸しシート）／`weekly_report.py`・`ops_dashboard.py` のLINE記入先を `state/line_inflow_manual.jsonl` へ | クラウドの週次企画が `state/line_inflow_manual.jsonl` を読めるようになる。投稿には影響なし |

- push済み。次回以降のpushは `git -c credential.helper= push https://<user>:<token>@github.com/hiro0183/threads-auto-post.git master:master`（Bashからの素の `git push` はGCMのダイアログが出せず止まる）
- 未コミット（残してよい）: `engage/2026-09-13.md`（デモ出力・架空候補と明記）／`posts/2026-09-13.json.bak_*`／`prompts/stories.md.bak_20260912`
- **実験台帳** `experiments/ledger.json` の W35-01〜03 は judge_on **2026-09-21**。02・03は baseline 無効。閉じるのは人間。次に開く3枚の案は `docs/…全施策.md` §5

**✅ 2026-09-14 検品NG18件を修正・push済み（コミット `2a1c583`）。**
- 対象: `posts/2026-09-15.json`・`posts/2026-09-16.json`・`posts/2026-09-17.json`・`posts/weekly_plan/2026-09-14.json`・`prompts/stories.md`・`prompts/persona.md`
- 内容: 14日以内の重複フック7枠（35,000円/15,000円/60分5,000円vs20分35,000円パターンの反復・cleft文の反復・同日内「任せたい気持ち」3回・「予約先を1つに絞る」2日前との重複・「あなたの院の次の一歩は、」の同日内重複・9/17 22:00導線枠の9/15との重複）を別の承認済み角度で作り直し。未取材（❓）の「15,000円時代に説明の順番を変えた」逸話を使っていた2枠（9/15 10:30・9/17 12:45）を差し替え。本文のみの修正3件（同日内の締め重複2件・同日内の技法重複2件）。17:00の「10連休」は本文はそのまま、出典（BNIプレゼン原稿・2026-09-11提出）付きで `stories.md` A-12・`persona.md` に承認済み事実として新規登録（追記のみ・上書きなし）。
- 検品: `check_hooks.py posts/weekly_plan/2026-09-14.json` 終了コード0（全7日OK）／`check_body_style.py` 3日分すべて終了コード0（NG・警告とも0件）
- `export_preview.py` は3日分実行済み（デスクトップ「コンサル投稿確認」へ出力）。`ops_dashboard.py` は内部で独自にgit commit/pushする作りのため、今回の指定コミットメッセージと衝突するのを避けてスキップ（次回の通常運用サイクルで自動実行される）

**✅ 2026-09-14 再発防止のガード3点を追加・push済み。**
- `check_hooks.py`: `check_same_day`（同日内の冒頭7字一致・8字/6字以上の共通部分文字列・自院価格の金額重複）と `check_history`（14日以内の類似度0.72・CTA枠のみ0.80／部分文字列11字以上／同じ金額+型が3周目）を新設。金額は「＃」に畳んでから比較（承認済み自院価格が実質2〜4種しかなく、生の金額文字列のままだと毎日誤検知するため）。`python check_hooks.py posts/weekly_plan/2026-09-14.json` は9/14〜9/17が全日OK。9/18〜9/20は合計32枠がNG（あと100万/バックエンド/全部やらなくていい/一番細い場所 等、総まとめ回で意図的に反復している言い回しが大半）。**修正の上限12枠を超えたため未修正のまま**、要人間確認としてセッションまとめに一覧を残した
- `check_body_style.py`: `CLOSING_NGRAM` を10→7字に短縮し、締めの「型」を正規表現7種でパターン化する `CLOSING_TEMPLATES` を新設（非CTAツリーで同型2本以上ならNG）。9/17 20:40の締め（「〜変えただけで、〜が変わりました」）を本文のみ修正し、9/15・9/16・9/17とも `check_body_style.py` 終了コード0
- `prompts/daily_writing_routine.md`・`CLAUDE.md`: 独立検品(12:00)が書く `posts/quality_gate/{date}_inspection.json` のうち**本文NGだけ**（`level:"body"`、またはreasonに「フック」等を含まないもの）を日次執筆便が翌朝自動で拾って2〜3投稿目だけ直す手順を新設（フック/事実NGは従来どおり人間確認）。上書き禁止ルールの唯一の例外として明記

**✅ 2026-09-14 積み残しの9/18〜9/20フック32枠NGを解消・commit待ち。**
- 上のブロック（同日）で「修正の上限12枠を超えたため未修正」と残っていた `check_hooks.py` の `check_same_day`/`check_history` NG（あと100万/バックエンド/全部やらなくていい/一番細い場所の反復）を全て別の承認済み角度・別の言い回しで作り直し（9/18=8枠・9/19=6枠・9/20=7枠、計21枠。同日重複の連鎖で自動的に解消された分を含む）
- `posts/2026-09-18.json`〜`2026-09-20.json` はまだクラウドの朝便が書いていないため存在せず（`check_body_style.py` の対象なし）。フックのみ差し替え・本文の上書きは発生していない
- 検品: `python check_hooks.py posts/weekly_plan/2026-09-14.json` 終了コード**0（9/14〜9/20の全7日OK）**

## 4. ⏸ なりあいさん待ち（本人にしかできない・この順で）

1. ~~Meta権限の有効化→再認証~~ **✅ 2026-09-14完了**（tokens.json＝hiro_nariai_salon_・scope 7つ・期限2026-11-13）。**ただし標準アクセスでは検索が自分の投稿しか返さない**→ App Review を出すか、Chrome＋Claudeで候補を拾う運用にするかを判断
2. 固定ポストを1本選んで投稿・固定（`prompts/pinned_post.md` 案A推奨。投稿日の22:00はCTA無しにする）
3. bio v3 に差し替え（「院長・社長へ」を残すか「院長へ」に絞るかは本人判断）
4. UTAGE で mtid=`uVqmOIrsLg8j` の週間LINE登録数を教える → `state/line_inflow_manual.jsonl` に記入（Claudeが代筆可）
5. 棚卸しシートの置き場を決める（UTAGE配布ページ／公開ページ／DMでPDF直送）→ URLを告知文・DM文へ
6. A4「会話5枠→2枠」の承認
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

- **🔴 再認証（`python threads_auth.py`）は、ブラウザで先にコンサル垢 `hiro_nariai_salon_`（ヒロ先生）にログインしてから。** 同意画面はブラウザに今ログインしている垢で出る。2026-09-14に産後垢（rapport.sango）でログインしたまま開いてしまい「rapport.sangoとして続行」が表示された（押す前に止めた・被害なし）。**同意画面の青いボタンが「hiro_nariai_salon_として続行」でなければ必ずキャンセル。** Metaアプリはコンサル=`自動投稿Threadsコンサル`／産後=`骨盤-8cm` で別物だが、産後垢がコンサルアプリに過去リンクした履歴が残っているので画面上は通ってしまう。安全策＝コンサル専用のChromeプロファイルかシークレットウィンドウで行う

- **keyword_search は標準アクセスだと自分の投稿しか返さない（2026-09-14実測）。** 他人の投稿を検索するには App Review（Advanced Access）が必要。それまで絡み候補は Chrome＋Claude セッションで拾う。トークンは「ユーザートークン生成ツール」で出すのが最短（`.env` のアプリシークレットは古い）。詳細 `engage/README.md`

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
