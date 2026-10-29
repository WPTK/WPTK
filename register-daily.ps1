# Registers the daily README refresh on Gilead. Rollback: Unregister-ScheduledTask -TaskName 'WPTK profile readme' -Confirm:$false
# Runs 7:00 AM local (Eastern) time while Bill is logged on. Books change after the Tuesday storygraph-sync run;
# planes change daily; GameDay changes when Wikipedia does. Commits and pushes only when README.md changed.
$ErrorActionPreference = 'Stop'
$root   = 'C:\WPTK'
$python = (Get-Command python).Source
$cmd    = "/c `"`"$python`" update.py --push >> update.log 2>&1`""

$action    = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $cmd -WorkingDirectory $root
$trigger   = New-ScheduledTaskTrigger -Daily -At 7:00AM
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName 'WPTK profile readme' -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Refresh the generated sections of the WPTK/WPTK GitHub profile README and push.' -Force
Get-ScheduledTask -TaskName 'WPTK profile readme' | Get-ScheduledTaskInfo | Select-Object NextRunTime
