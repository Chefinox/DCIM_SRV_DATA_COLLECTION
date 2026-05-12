# Metric Documentation: Mikrotik (SNMP)

**Sources**: FIT-Core, FIT-Dist Subnets (172.16.35.x)
**Collector**: Telegraf SNMP Input (Existing)

| Metric Field | Description |
|---|---|
| `system_name` | Hostname of the router/switch |
| `system_uptime` | Time since last reboot |
| `cpu_load` | Current CPU load (%) |
| `memory_total_kb` | Total RAM available |
| `memory_used_kb` | Currently used RAM |
| `net_interface.if_name` | Interface Name (ether1, sfp-sfpplus1, etc.) |
| `net_interface.if_speed` | Link Speed (bps) |
| `net_interface.if_in_octets` | Traffic RX (Total) |
| `net_interface.if_out_octets` | Traffic TX (Total) |
| `net_interface.if_in_errors` | RX Errors |
| `net_interface.if_out_errors` | TX Errors |
