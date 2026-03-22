@echo off
REM 事前生成した投稿ファイルをGitHubにプッシュする
REM 内容確認・編集後に実行してください

cd C:\Users\tujid\threads_tool

echo 投稿ファイルをGitHubに送信中...

git add posts/*.json
git add posts/*.txt
git add post_runner.py
git add generate_daily_posts.py
git add generate_bulk_posts.py
git commit -m "投稿ファイル更新 %date%"
git push

echo.
echo 送信完了！次の投稿からファイルの内容が使われます
pause
