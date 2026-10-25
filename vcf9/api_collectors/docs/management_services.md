# vCenter appliance DNS, NTP and log forwarding

Author: Paul Bryant

Collect the configured DNS servers and mode, NTP servers, time synchronization mode and remote log forwarding destinations from selected vCenter appliances. These optional resources use GET requests only. They do not run network tests or change settings.

```powershell
python collect_vcf.py --component vcenter --config examples/management-services.example.json --output ./inventory
python report_management_services.py --run ./inventory/<completed-run> --baseline examples/management-services-baseline.example.json --output ./reports/management-services.json --csv
```

Use the completed run directory printed by the collector. Supply credentials through the environment variables named by the configuration. Normal TLS verification applies; configure the existing `verify_tls` CA bundle option for an internal certificate authority.

The collection resources are `appliance_dns`, `appliance_ntp`, `appliance_timesync` and `appliance_syslog`. Each resource stores a single `configuration` record, even when its server list is empty. No arbitrary filters are accepted. Selecting these resources leaves the standard vCenter inventory defaults unchanged.

The optional baseline identifies each appliance by its exact saved target name and HTTPS endpoint. Every entry specifies one or more of `dns`, `ntp`, `timesync` and `syslog`. The example shows all four. An empty server list is an explicit expected configuration. Omit a service to observe its settings without assessing it against a baseline. Unknown fields, duplicate target selectors and malformed service configurations are rejected.

Server list order is ignored during comparison. Hostnames, address strings, case, native modes, ports and protocols otherwise compare exactly. Use the native mode and protocol strings returned by the appliance. A difference produces a `review` observation; it does not automatically establish a service outage. Without a baseline, configuration is `observed` and `baseline_match` remains null.

The DNS example uses the native `is_static` value documented by the appliance networking SDK; the corresponding DHCP value is `dhcp`. Confirm the observed native value for the installed build when setting a baseline.

A failed, missing, duplicated or malformed saved resource produces an `unknown` observation and a partial report. An expected target missing from the saved run also remains unknown. Report success describes the availability of evidence, including observed baseline differences.

These are appliance configuration checks. They do not establish DNS resolution, NTP clock offset or synchronization, receiver reachability, certificate validity at a log receiver, or successful log delivery. NTP servers can remain configured when time synchronization uses another mode, so inspect the separate `timesync` result. The report describes saved collection time and does not assert current appliance state.

This initial scope covers vCenter appliances. ESXi hosts, SDDC Manager, NSX and other management appliances require separate product-specific endpoints and are outside this report. The documented APIs provide configuration access; installed-build and privilege behavior still requires live validation.

Public API references:

- [DNS server configuration](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/appliance/networking/dns/servers/get/)
- [Appliance networking SDK and DNS mode enumeration](https://dp-downloads-pstg.broadcom.com/api-content/apis/API_VAA_003/Python%208.0/html/8.0.0.1/com.vmware.appliance.networking.html)
- [NTP configuration and the distinction from time synchronization mode](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/appliance/ntp/get/)
- [Time synchronization mode](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/appliance/timesync/get/)
- [Remote log forwarding configuration](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/appliance/logging/forwarding/get/)
