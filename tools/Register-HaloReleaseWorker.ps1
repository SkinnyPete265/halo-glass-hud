$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python.exe -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
$script = Join-Path $PSScriptRoot 'local_release.py'
$taskName = 'Halo HUD local release worker'
if (!(Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw 'pythonw.exe is required for background polling.' }
& $python -B $script setup
if ($LASTEXITCODE -ne 0) { throw 'Worker setup failed.' }
$action = New-ScheduledTaskAction -Execute $pythonw -Argument ('-B "{0}" poll' -f $script) -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 3)
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "$taskName registered for the signed-in user."
