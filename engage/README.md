# 絡み部門（engage）

## 目的

@hiro_nariai_salon_ はフォロワー911人で2ヶ月横ばい、実質エンゲージ率0.07%、読者返信ほぼゼロ。
全投稿が自動化されていて、人間が一度も他アカウントに絡んでいない。「絡み」が唯一未着手の
成長レバーで、それを1日10分でできる形にしたのがこのフォルダの仕組み。

詳しいルール（量・優先順・返信の型・NG）は `prompts/engage_rules.md` を参照。

## 毎日の10分の手順

1. 朝、`engage/YYYY-MM-DD.md`（今日の日付）を開く
2. 「0. まず返す」に載っている読者返信があれば最優先で先に返す
3. 「1. 今日の候補」を上から5件、A案かB案をそのまま or 少し直して貼り付けて返信する
4. 終わったら `python engage_list.py --done ID1 ID2 ...`（返信したIDを渡す）を実行、または何もしなくても72時間を過ぎれば自動的に候補から消える
5. 5件やれば終わり（無理に全部やらない）

候補は毎朝06:40 JSTに自動更新される（`.github/workflows/engage_candidates.yml`）。
下書き（AI呼び出し）はローカルで `python engage_list.py --draft-only` を実行して作る。

## scope有効化〜再認証の手順

1. Metaアプリのダッシュボードで `threads_keyword_search` と `threads_profile_discovery` を有効化する
2. `python threads_auth.py` で再認証する（`threads_auth.py` のSCOPESに追加済み）
3. `python token_manager.py --seed` で新トークンをDBへ発行する
4. GitHub Actionsのsecret `THREADS_ACCESS_TOKEN` とRenderの環境変数を新トークンに差し替える
5. それまでは `python engage_list.py --search-only` を実行しても候補0件のまま正常終了する（エラーにはならない）

## NG（禁じ手・詳細は prompts/engage_rules.md）

- 定型文のコピペ
- 宣伝・LINE誘導・商品名
- 「AI」を主語にする
- 相手の否定・添削
- 長文
- 架空の数字・体験
- 保険診療の話
- 「実は」書き出し
- 同じ相手に1日2回

## 自動投稿しない

**返信の送信は必ず人間の手で行う。このスクリプトは絶対に返信を自動投稿しない。**
`engage_list.py` はどのモードでも下書きの生成・保存までしか行わず、Threads APIへの投稿（POST）は一切呼ばない。
