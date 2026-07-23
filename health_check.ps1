# Threads自動化タスクのヘルスチェック（毎朝04:55自動実行）
# 6つの定期タスクの前回実行結果をObsidianに書き出す。
# 0x0=成功 / それ以外=失敗（0x800710E0=電源設定等でキャンセル, 0x80070002=ファイル未発見）

$tasks = @(
    "Threads_TrackFollowers",
    "Threads_PullInsights",
    "Threads_CollectInsights",
    "Threads_DailyPlanPipeline",
    "Threads_AnalyzePatterns",
    "Threads_SavePostsToObsidian",
    "Threads_MorningInspection",
    "Threads_NoonInspection",
    "IG_StoryRender",
    "IG_StoryWeekly",
    "Threads_OpsDashboard",
    "Threads_WeeklyReport",
    "Threads_WeeklySession",
    "Threads_MondayCatchup",
    "Rapport_PreviewExport",
    "Rapport_StoryWeekly"
)
# 週次タスク（月曜のみ実行）は日次の総合判定から除外する
$weeklyTasks = @("Threads_WeeklyReport", "Threads_WeeklySession", "Threads_MondayCatchup", "IG_StoryWeekly", "Rapport_StoryWeekly")
# 予備タスク（意図的に無効化。日次生成はクラウドルーティンが正・2026-07-17決定）
# 無効でも⏸表示にして総合判定から除外する（⛔❌にしない）
$backupTasks = @("Threads_DailyPlanPipeline")

$outFile = "C:\Users\tujid\OneDrive\Desktop\HIRAYASU\コンサルThreads\インサイト\_自動実行ヘルスチェック.md"
$logFile = "C:\Users\tujid\threads_tool\health_check_history.log"
$now = Get-Date -Format "yyyy-MM-dd HH:mm"

$lines = @()
$lines += "# 自動実行ヘルスチェック"
$lines += ""
$lines += "> 最終チェック: $now（毎朝04:55に自動更新）"
$lines += ""
$lines += "| タスク | 状態 | 前回実行 | 結果 | 判定 |"
$lines += "|:---|:---:|:---|:---|:---:|"

$allOk = $true
$summary = @()

foreach ($name in $tasks) {
    try {
        $task = Get-ScheduledTask -TaskName $name -ErrorAction Stop
        $info = $task | Get-ScheduledTaskInfo
        $result = $info.LastTaskResult
        $hex = "0x{0:X}" -f $result
        # 無効化されたタスクは「前回結果0x0のまま」なので、結果だけ見ると✅に見えてしまう。
        # 実際には動いていないので失敗として扱う（2026-07-17: DailyPlanPipelineの停止を9日間見逃した）
        $disabled = ($task.State -eq "Disabled")
        $isBackup = ($backupTasks -contains $name)
        $neverRan = ($result -eq 0x41303)  # 登録直後でまだ一度も実行されていない＝異常ではない
        # チェックの瞬間にタスクがまだ走っていると LastTaskResult は 0x41301(SCHED_S_TASK_RUNNING) になる。
        # これは失敗ではない（04:55のヘルスチェックが朝タスクの「実行中スナップショット」を掴んだだけ）。
        # 以前はこれを❌と数えて総合判定が毎回赤くなる誤報が出ていた（2026-07-21修正）。
        $running = ($result -eq 0x41301) -or ($task.State -eq "Running")
        $ok = ($result -eq 0) -and (-not $disabled)
        if (-not $ok -and ($weeklyTasks -notcontains $name) -and (-not $isBackup) -and (-not $neverRan) -and (-not $running)) { $allOk = $false }
        # 週次タスクは日次の総合判定から除外（結果自体は表示する）
        $mark = if ($isBackup -and $disabled) { "⏸" } elseif ($ok) { "✅" } elseif ($disabled) { "⛔" } elseif ($neverRan) { "⏸" } elseif ($running) { "🔄" } else { "❌" }
        $lines += "| $name | $($task.State) | $($info.LastRunTime) | $hex | $mark |"
        $summary += "$name=$hex"
    } catch {
        $lines += "| $name | 未登録 | - | - | ❌ |"
        $allOk = $false
        $summary += "$name=MISSING"
    }
}

$lines += ""
if ($allOk) {
    $lines += "**総合判定: ✅ すべて正常です。何もする必要はありません。**"
} else {
    $lines += "**総合判定: ❌ 失敗しているタスクがあります。Claude Codeセッションで「ヘルスチェックが失敗してる、調べて」と伝えてください。**"
    $lines += ""
    $lines += "- よくある原因: PCがスリープ中でタスクが起動できなかった（WakeToRun設定を確認）／バッテリー切れ／スクリプトエラー"
    $lines += "- **⛔ = タスクが無効化されている**（そもそも動いていない。有効化が必要）"
    $lines += "- ⏸ = 予備タスク（意図的に無効化中。異常ではありません）"
}
$lines += ""
$lines += "## 見方"
$lines += ""
$lines += "- 0x0 = 成功"
$lines += "- 🔄 / 0x41301 = チェック時にまだ実行中だった（失敗ではない・数分後には完了）"
$lines += "- 0x800710E0 = 電源設定などで実行がキャンセルされた"
$lines += "- 0x80070002 = 実行ファイルが見つからなかった"
$lines += "- 0x41303 = まだ一度も実行されていない"

Set-Content -Path $outFile -Value ($lines -join "`n") -Encoding UTF8

# 履歴も1行ログとして残す（過去の傾向を追えるように）
$status = if ($allOk) { "OK" } else { "NG" }
Add-Content -Path $logFile -Value "$now [$status] $($summary -join ' / ')" -Encoding UTF8
