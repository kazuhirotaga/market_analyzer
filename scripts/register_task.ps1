# Market Analyzer デイリー実行タスク登録スクリプト
# Windowsタスクスケジューラに毎日18:00実行のタスクを登録します

$TaskName = "MarketAnalyzerDaily"
$PythonPath = "$PSScriptRoot\..\.venv\Scripts\python.exe"
$ScriptPath = "$PSScriptRoot\run_daily.py"
$WorkDir = "$PSScriptRoot\.."

# パスの解決
$PythonPath = Resolve-Path $PythonPath
$ScriptPath = Resolve-Path $ScriptPath
$WorkDir = Resolve-Path $WorkDir

Write-Host "以下の設定でタスクを登録します:"
Write-Host "  タスク名: $TaskName"
Write-Host "  実行:     $PythonPath"
Write-Host "  引数:     $ScriptPath"
Write-Host "  作業Dir:  $WorkDir"
Write-Host "  時間:     毎日 18:00"

$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument $ScriptPath -WorkingDirectory $WorkDir
$Trigger = New-ScheduledTaskTrigger -Daily -At "18:00"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# タスク登録 (要管理者権限)
try {
    Register-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings -TaskName $TaskName -Description "Market Analyzer Daily Run" -Force
    Write-Host "`n✅ タスク登録完了! 毎日18:00に自動実行されます。" -ForegroundColor Green
} catch {
    Write-Host "`n❌ エラー: タスク登録に失敗しました。管理者権限で実行してください。" -ForegroundColor Red
    Write-Host $_
}
