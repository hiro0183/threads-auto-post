# 同梱フォントについて

`NotoSansJP-VF.ttf` / `NotoSansJP-Bold.ttf` は Google の Noto Sans Japanese。
ライセンスは **SIL Open Font License 1.1**（再配布可）。
https://fonts.google.com/noto/specimen/Noto+Sans+JP

## なぜリポジトリに入れているか

IGストーリーのPNG生成（`render_story.py`）が、以前は Windows のシステムフォント
（`C:\Windows\Fonts\meiryo.ttc` 等）に依存していたため、**このPCが起動していないと
画像が作れませんでした**。フォントを同梱することで、クラウド（claude.ai/code の
セッションやルーティン）からも同じ画像が生成できます。

※ Meiryo は Microsoft の製品同梱フォントで再配布できないため、本文フォントを
Noto Sans JP（Regular相当）に変更しました。
