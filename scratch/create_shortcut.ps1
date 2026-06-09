$desktopPath = [Environment]::GetFolderPath("Desktop")
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$desktopPath\Spark.lnk")
$Shortcut.TargetPath = "C:\Users\pavan\odysseus\launch-spark.vbs"
$Shortcut.WorkingDirectory = "C:\Users\pavan\odysseus"
$Shortcut.IconLocation = "C:\Users\pavan\odysseus\static\icon.ico"
$Shortcut.Save()
Write-Output "Shortcut successfully created on Desktop at $desktopPath!"
