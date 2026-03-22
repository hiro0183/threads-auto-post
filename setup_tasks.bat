@echo off
REM Threads自動投稿 タスクスケジューラ設定スクリプト
REM 管理者権限で実行してください

SET PYTHON=py
SET SCRIPT=C:\Users\tujid\threads_tool\post_runner.py

echo Threads自動投稿タスクを登録中...

schtasks /create /tn "Threads_Post_0545" /tr "%PYTHON% %SCRIPT%" /sc daily /st 05:45 /f
schtasks /create /tn "Threads_Post_0600" /tr "%PYTHON% %SCRIPT%" /sc daily /st 06:00 /f
schtasks /create /tn "Threads_Post_0700" /tr "%PYTHON% %SCRIPT%" /sc daily /st 07:00 /f
schtasks /create /tn "Threads_Post_0730" /tr "%PYTHON% %SCRIPT%" /sc daily /st 07:30 /f
schtasks /create /tn "Threads_Post_0800" /tr "%PYTHON% %SCRIPT%" /sc daily /st 08:00 /f
schtasks /create /tn "Threads_Post_0830" /tr "%PYTHON% %SCRIPT%" /sc daily /st 08:30 /f
schtasks /create /tn "Threads_Post_0900" /tr "%PYTHON% %SCRIPT%" /sc daily /st 09:00 /f
schtasks /create /tn "Threads_Post_0930" /tr "%PYTHON% %SCRIPT%" /sc daily /st 09:30 /f
schtasks /create /tn "Threads_Post_1000" /tr "%PYTHON% %SCRIPT%" /sc daily /st 10:00 /f
schtasks /create /tn "Threads_Post_1100" /tr "%PYTHON% %SCRIPT%" /sc daily /st 11:00 /f
schtasks /create /tn "Threads_Post_1200" /tr "%PYTHON% %SCRIPT%" /sc daily /st 12:00 /f
schtasks /create /tn "Threads_Post_1230" /tr "%PYTHON% %SCRIPT%" /sc daily /st 12:30 /f
schtasks /create /tn "Threads_Post_1300" /tr "%PYTHON% %SCRIPT%" /sc daily /st 13:00 /f
schtasks /create /tn "Threads_Post_1400" /tr "%PYTHON% %SCRIPT%" /sc daily /st 14:00 /f
schtasks /create /tn "Threads_Post_1500" /tr "%PYTHON% %SCRIPT%" /sc daily /st 15:00 /f
schtasks /create /tn "Threads_Post_1600" /tr "%PYTHON% %SCRIPT%" /sc daily /st 16:00 /f
schtasks /create /tn "Threads_Post_1700" /tr "%PYTHON% %SCRIPT%" /sc daily /st 17:00 /f
schtasks /create /tn "Threads_Post_1800" /tr "%PYTHON% %SCRIPT%" /sc daily /st 18:00 /f
schtasks /create /tn "Threads_Post_1830" /tr "%PYTHON% %SCRIPT%" /sc daily /st 18:30 /f
schtasks /create /tn "Threads_Post_1900" /tr "%PYTHON% %SCRIPT%" /sc daily /st 19:00 /f
schtasks /create /tn "Threads_Post_1915" /tr "%PYTHON% %SCRIPT%" /sc daily /st 19:15 /f
schtasks /create /tn "Threads_Post_1930" /tr "%PYTHON% %SCRIPT%" /sc daily /st 19:30 /f
schtasks /create /tn "Threads_Post_2000" /tr "%PYTHON% %SCRIPT%" /sc daily /st 20:00 /f
schtasks /create /tn "Threads_Post_2015" /tr "%PYTHON% %SCRIPT%" /sc daily /st 20:15 /f
schtasks /create /tn "Threads_Post_2020" /tr "%PYTHON% %SCRIPT%" /sc daily /st 20:20 /f
schtasks /create /tn "Threads_Post_2040" /tr "%PYTHON% %SCRIPT%" /sc daily /st 20:40 /f
schtasks /create /tn "Threads_Post_2100" /tr "%PYTHON% %SCRIPT%" /sc daily /st 21:00 /f
schtasks /create /tn "Threads_Post_2120" /tr "%PYTHON% %SCRIPT%" /sc daily /st 21:20 /f
schtasks /create /tn "Threads_Post_2140" /tr "%PYTHON% %SCRIPT%" /sc daily /st 21:40 /f
schtasks /create /tn "Threads_Post_2200" /tr "%PYTHON% %SCRIPT%" /sc daily /st 22:00 /f

REM トークン自動更新（毎月1日 AM5:00）
schtasks /create /tn "Threads_TokenRefresh" /tr "%PYTHON% %SCRIPT% --refresh" /sc monthly /d 1 /st 05:00 /f

echo.
echo 投稿タスク登録完了（30件/日 + 月次トークン更新）
pause
