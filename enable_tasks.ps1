$tasks = Get-ScheduledTask | Where-Object TaskName -like 'Threads_Post_*' | Where-Object State -eq 'Disabled'
foreach ($task in $tasks) {
    Enable-ScheduledTask -TaskName $task.TaskName | Out-Null
    Write-Host "[有効化] $($task.TaskName)"
}
Write-Host ""
Write-Host "完了: $($tasks.Count) 件を有効化しました"
