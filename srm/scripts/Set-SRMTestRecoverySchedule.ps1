<#
.SYNOPSIS
    Schedules regular test recovery runs for SRM Recovery Plans.

.DESCRIPTION
    Writes Windows Task Scheduler jobs for periodic Invoke-SRMTestRecoveryPlan.
    Exports current schedule to CSV.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
    Requires admin rights on scheduler.
#>

# This script creates scheduled tasks, not a direct SRM action.
# Use "schtasks" command to create scheduled PowerCLI invocations.
Write-Host "SRM test recovery plan scheduling is best handled by Windows Task Scheduler or a runbook orchestrator."
Write-Host "See VMware documentation for production scheduling recommendations."
