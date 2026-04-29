# Metric Documentation: APC UPS (SNMP)

**Source**: 192.168.100.140
**Collector**: Telegraf SNMP Input
**Index**: `telegraf-metrics-*` (Default Telegraf Output)

| Metric Field | Description | OID |
|---|---|---|
| `model` | UPS Model Name | .1.3.6.1.4.1.318.1.1.1.1.1.1.0 |
| `status` | Current Status (2=OnLine, 3=OnBattery) | .1.3.6.1.4.1.318.1.1.1.4.1.1.0 |
| `battery_capacity` | Battery Charge Percentage (%) | .1.3.6.1.4.1.318.1.1.1.2.2.1.0 |
| `battery_runtime_remain` | Runtime Remaining (Minutes) | .1.3.6.1.4.1.318.1.1.1.2.2.3.0 |
| `battery_temp` | Internal Battery Temperature (C) | .1.3.6.1.4.1.318.1.1.1.2.2.2.0 |
| `input_voltage` | Incoming Line Voltage (V) | .1.3.6.1.4.1.318.1.1.1.3.2.1.0 |
| `output_voltage` | Outgoing Voltage (V) | .1.3.6.1.4.1.318.1.1.1.4.2.1.0 |
| `output_load` | Output Load Percentage (%) | .1.3.6.1.4.1.318.1.1.1.4.2.3.0 |
