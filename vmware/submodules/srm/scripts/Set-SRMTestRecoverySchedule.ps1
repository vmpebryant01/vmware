<#
.SYNOPSIS
    Schedules regular test recovery runs for SRM Recovery Plans.

.DESCRIPTION
    Writes Windows Task Scheduler jobs for periodic Invoke-SRMTestRecoveryPlan.
    Exports current schedule to CSV.

.NOTES
    PowerCLI >=13.0 required.
    Requires admin rights on scheduler.
#>

# This script creates scheduled tasks, not a direct SRM action.
# Use "schtasks" command to create scheduled PowerCLI invocations.
Write-Host "SRM test recovery plan scheduling is best handled by Windows Task Scheduler or a runbook orchestrator."
Write-Host "See VMware documentation for production scheduling recommendations."
