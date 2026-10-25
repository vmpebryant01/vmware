"""Read-only operational reports from completed saved runs. Author: Paul Bryant."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .exports import sanitize, write_json, write_resource
from .report_support import read_policy
from .runs import RunError, load_run

REPORTS = ("backup_freshness", "protection_gaps", "vsan_health", "hcx_migrations",
           "access_permissions", "nsx_rule_usage", "automation_requests", "lifecycle_compliance",
           "management_services", "metric_history", "supervisor_health")


def _option(options, name, default):
    return default if options.get(name) is None else options[name]


def build_report(report_type, run, previous=None, **options):
    if report_type == "lifecycle_compliance":
        from .lifecycle_report import build_lifecycle_report
        return build_lifecycle_report(run, max_scan_age_hours=_option(options, "max_scan_age_hours", 24), now=options.get("now"))
    if report_type == "management_services":
        from .management_services_report import build_management_services_report
        return build_management_services_report(run, baseline=options.get("baseline"))
    if report_type == "metric_history":
        from .metric_history_report import build_metric_history_report
        return build_metric_history_report(run)
    if report_type == "supervisor_health":
        from .supervisor_report import build_supervisor_report
        return build_supervisor_report(run, max_used_percent=_option(options, "max_used_percent", 80))
    if report_type in ("backup_freshness", "access_permissions"):
        from .assurance_reports import build_access_report, build_backup_report
        if report_type == "backup_freshness":
            return build_backup_report(run, max_age_hours=_option(options, "max_age_hours", 24), now=options.get("now"),
                                       nsx_time_unit=options.get("nsx_time_unit"))
        return build_access_report(run, baseline=options.get("baseline"),
                                   broad_privilege_threshold=_option(options, "broad_privilege_threshold", 100))
    if report_type == "vsan_health":
        from .vsan_report import build_vsan_report
        return build_vsan_report(run, max_used_percent=_option(options, "max_used_percent", 80))
    if report_type == "protection_gaps":
        from .protection_report import build_protection_report
        return build_protection_report(run, options.get("policy"), now=options.get("now"))
    from .activity_reports import build_automation_report, build_hcx_report, build_nsx_usage_report
    if report_type == "hcx_migrations":
        return build_hcx_report(run, previous=previous, stalled_minutes=_option(options, "stalled_minutes", 30),
                                hcx_time_unit=options.get("hcx_time_unit"))
    if report_type == "nsx_rule_usage":
        return build_nsx_usage_report(run, previous=previous)
    if report_type == "automation_requests":
        return build_automation_report(run, long_running_minutes=_option(options, "long_running_minutes", 60), now=options.get("now"))
    raise ValueError("Unknown report type.")


def main(argv=None, report_type=None):
    parser = argparse.ArgumentParser(description="Build read-only operational reports from a completed inventory run.")
    if report_type is None:
        parser.add_argument("--report", choices=REPORTS, required=True)
    parser.add_argument("--run", required=True, type=Path, help="Completed collection run directory")
    parser.add_argument("--output", required=True, type=Path, help="Report JSON outside source run directories")
    parser.add_argument("--csv", action="store_true", help="Also write a records JSON/CSV pair")
    parser.add_argument("--previous", type=Path, help="Earlier completed run for HCX progress or NSX counters")
    parser.add_argument("--policy", type=Path, help="Protection requirements JSON, required for protection gaps")
    parser.add_argument("--baseline", type=Path, help="Access-assignment or management-service baseline JSON")
    parser.add_argument("--max-age-hours", type=float, help="Backup freshness threshold, default 24 hours")
    parser.add_argument("--max-used-percent", type=float, help="vSAN or Supervisor capacity review threshold, default 80 percent")
    parser.add_argument("--max-scan-age-hours", type=float, help="Cached lifecycle scan age threshold, default 24 hours")
    parser.add_argument("--stalled-minutes", type=float, help="HCX unchanged-progress observation interval, default 30 minutes")
    parser.add_argument("--long-running-minutes", type=float, help="Automation request age threshold, default 60 minutes")
    parser.add_argument("--broad-privilege-threshold", type=int, help="Access role privilege-count review threshold, default 100")
    parser.add_argument("--nsx-time-unit", choices=("milliseconds",), help="Operator-confirmed NSX backup epoch unit; otherwise freshness remains unknown")
    parser.add_argument("--hcx-time-unit", choices=("milliseconds", "seconds"), help="Operator-confirmed HCX migration epoch unit; otherwise elapsed duration remains unknown")
    args = parser.parse_args(argv)
    selected = report_type or args.report
    try:
        allowed_options = {
            "backup_freshness": {"max_age_hours", "nsx_time_unit"}, "protection_gaps": {"policy"}, "vsan_health": {"max_used_percent"},
            "hcx_migrations": {"previous", "stalled_minutes", "hcx_time_unit"}, "access_permissions": {"baseline", "broad_privilege_threshold"},
            "nsx_rule_usage": {"previous"}, "automation_requests": {"long_running_minutes"},
            "lifecycle_compliance": {"max_scan_age_hours"}, "management_services": {"baseline"},
            "metric_history": set(), "supervisor_health": {"max_used_percent"},
        }
        if selected not in allowed_options:
            raise ValueError("Unknown report type.")
        for field in ("max_age_hours", "max_used_percent", "stalled_minutes", "long_running_minutes",
                      "broad_privilege_threshold", "policy", "baseline", "previous", "nsx_time_unit", "hcx_time_unit", "max_scan_age_hours"):
            if getattr(args, field) is not None and field not in allowed_options[selected]:
                raise ValueError("An option does not apply to the selected report.")
        if selected == "protection_gaps" and args.policy is None:
            raise ValueError("Protection gaps require --policy with explicitly identified expected VMs.")
        output = args.output.resolve()
        outputs = {output}
        if args.csv:
            outputs.update(output.parent / (output.stem + "_records" + suffix) for suffix in (".json", ".csv"))
        sources = [args.run] + ([args.previous] if args.previous else [])
        if any(destination.is_relative_to(source.resolve()) for destination in outputs for source in sources):
            raise ValueError("Write reports outside both input run directories.")
        if any(path and path.resolve() in outputs for path in (args.policy, args.baseline)):
            raise ValueError("Report output must not replace a policy or baseline.")
        run = load_run(args.run)
        previous = load_run(args.previous) if args.previous else None
        now = datetime.now(timezone.utc)
        report = build_report(selected, run, previous=previous, now=now,
                              policy=read_policy(args.policy) if args.policy else None,
                              baseline=read_policy(args.baseline) if args.baseline else None,
                              max_age_hours=args.max_age_hours, max_used_percent=args.max_used_percent,
                              stalled_minutes=args.stalled_minutes, long_running_minutes=args.long_running_minutes,
                              broad_privilege_threshold=args.broad_privilege_threshold,
                              nsx_time_unit=args.nsx_time_unit, hcx_time_unit=args.hcx_time_unit,
                              max_scan_age_hours=args.max_scan_age_hours)
        if not isinstance(report, dict) or not isinstance(report.get("records"), list):
            raise ValueError("Report builder returned invalid records.")
        report.update(author="Paul Bryant", evaluated_at=now.isoformat(timespec="seconds"),
                      record_count=len(report["records"]), source_completed_at=run["summary"]["completed_at"],
                      source_run_status=run["summary"]["status"])
        if previous:
            report["previous_completed_at"] = previous["summary"]["completed_at"]
        report = sanitize(report)
        if args.csv:
            metadata = {key: value for key, value in report.items() if key != "records"}
            write_resource(output.parent, output.stem + "_records", report["records"], metadata, write_csv=True)
        write_json(output, report)
        print(f"Report: {output}")
        return 0 if report.get("status") == "success" else 2
    except (RunError, ValueError) as exc:
        print(f"Cannot build report: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("Cannot read a report input or write the requested output.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
