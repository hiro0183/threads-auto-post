$python = 'C:\Users\tujid\AppData\Local\Programs\Python\Python312\python.exe'
$script = 'C:\Users\tujid\threads_tool\post_runner.py'
$user   = 'tujid'

$new_slots = @(
    '05:00','05:15','05:30','06:30','09:45',
    '10:15','10:30','11:30','12:45','13:15',
    '13:30','14:30','15:30','16:30','16:45',
    '17:30','18:15','18:45','19:45','21:50'
)

foreach ($slot in $new_slots) {
    $hhmm    = $slot -replace ':',''
    $name    = "Threads_Post_$hhmm"
    $start   = "2026-03-30T${slot}:00"

    $action  = New-ScheduledTaskAction -Execute $python -Argument "`"$script`""
    $trigger = New-ScheduledTaskTrigger -Daily -At $start
    $prin    = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $prin -Force | Out-Null
    Write-Host "[OK] $name ($slot)"
}
Write-Host ""
Write-Host "登録完了: $($new_slots.Count) 件"
