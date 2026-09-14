# UTAGE のLINE登録数を週1で読む手順（2026-09-14 新設・Claudeがブラウザで実行）

> UTAGEにAPIは無い。**なりあいさんがChromeでUTAGEにログインした状態**で、Claude（Chrome拡張）が以下を実行する。所要2分。
> 記入先: `state/line_inflow_manual.jsonl`（`week_start` は月曜日付・`line_additions` が登録数）。週次レポート §7 と司令室が読む。

1. タブで `https://utage-system.com/account/JHy3PzhXQLu3/scenario/QBooAfM2qWKZ/tracking/data` を開く（ログイン画面が出たら本人にログインしてもらう）
2. JSで期間を入れて「表示」を押す（URLのクエリは無視されるのでJSで）:
   ```js
   const f=document.querySelector('input[name="date_from"]'),t=document.querySelector('input[name="date_to"]');
   f.value='2026-09-14'; t.value='2026-09-20'; f.dispatchEvent(new Event('change',{bubbles:true})); t.dispatchEvent(new Event('change',{bubbles:true}));
   document.querySelector('#search').click();
   ```
3. 2秒待って `get_page_text` → 「新LP_AI設計セッション  PV UU 登録数」の行を読む
4. `state/line_inflow_manual.jsonl` に追記（`line_additions`=登録数・`pv`・`uu`・`source`:"utage_tracking_data"）→ commit → push

## 実測（初回 2026-09-14）
| 週 | PV | UU | 登録 |
|:--|--:|--:|--:|
| 2026-08-31〜09-06 | 3 | 1 | 1 |
| 2026-09-07〜09-13 | 1 | 1 | 1 |
| 累計（8/6〜） | 4 | 2 | 2 |

→ Threads→LP→LINE は**週1人**。LPのPVが週1〜3＝プロフィールのリンクを押す人がほぼいない。伸ばすのはLPではなく「プロフィールに来てリンクを押す人」（固定投稿・bio・絡み）。

## 🔴 同時に見つかった異常（2026-09-14）
UTAGE画面の赤帯: **「LINE公式アカウントの通数が送信上限に到達しました…LINE配信がエラーとなります」対象: ヒロ先生｜オンラインダイエットコーチ(@634vchhg)**。
この配信アカウントに紐づくLINE公式が月の送信上限に達している＝**問診導線のステップ3通（登録直後／1日後／3日後）が届かない可能性**。9/11に設置したダイエットLINE30通の配信が同じLINE公式を使っていれば、それが上限を食った疑い。**LINE公式アカウント管理画面でプラン変更（または追加メッセージ購入）→ UTAGE右上の更新アイコン**。本人にしかできない。
