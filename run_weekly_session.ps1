# 週次企画セッションの自動実行ラッパー（毎週月曜05:10・タスク: Threads_WeeklySession）
# Claude Code をヘッドレスモードで起動し、週次企画を作らせる。
# ANTHROPIC_API_KEY を明示的に除外し、Maxプラン（claude.aiログイン）側で実行する。
#
# モデル: Opus 4.8（2026-07-09にFable 5から変更。フック210本はルールブック駆動の型作業で
# Opusで十分と判断。品質劣化は週次レポートのホームラン監視が自動検知する。
# 劣化が出たら下の --model opus を --model fable に戻すだけ）

$ErrorActionPreference = "Continue"
Set-Location "C:\Users\tujid\threads_tool"

Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue

$logFile = "C:\Users\tujid\threads_tool\weekly_session.log"
$now = Get-Date -Format "yyyy-MM-dd HH:mm"
Add-Content -Path $logFile -Value "===== $now 週次企画セッション開始 ====="

$prompt = Get-Content "C:\Users\tujid\threads_tool\weekly_session_prompt.md" -Raw -Encoding UTF8

# --permission-mode acceptEdits: ファイルの読み書きは自動許可（Bash等は不可のまま）
& claude --model opus --permission-mode acceptEdits -p $prompt 2>&1 |
    Tee-Object -Variable output | Add-Content -Path $logFile

$now2 = Get-Date -Format "yyyy-MM-dd HH:mm"
Add-Content -Path $logFile -Value "===== $now2 終了 (exit=$LASTEXITCODE) ====="

# 司令室を最新化（企画結果を反映）
& "C:\Users\tujid\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\tujid\threads_tool\ops_dashboard.py" 2>&1 | Add-Content -Path $logFile

exit $LASTEXITCODE
