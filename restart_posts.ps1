# Threads自動投稿 再開スクリプト（2026-03-28 実行用）
Get-ScheduledTask | Where-Object { $_.TaskName -like 'Threads_Post*' } | Enable-ScheduledTask | Out-Null

# 実行ログ
$logPath = "C:\Users\tujid\threads_tool\restart_log.txt"
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Threads_Post 30件を再有効化しました" | Out-File -FilePath $logPath -Append

# このタスク自体を削除（1回限り実行）
Unregister-ScheduledTask -TaskName "Threads_RestartPosts" -Confirm:$false
