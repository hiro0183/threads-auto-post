$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("C:\Users\tujid\OneDrive\Desktop\Threads投稿ファイル.lnk")
$sc.TargetPath = "C:\Users\tujid\threads_tool\posts"
$sc.Save()
