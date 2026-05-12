# Exhaustive Metrics Inventory — Full Hardware Capability

This document lists **all** potential data points available from the devices in the DCIM project.

## 1. APC UPS (PowerNet-MIB)
Beyond the standard status, the following groups are available in the full MIB:
- **UPS Unit**: Model, Name, Serial, Firmware, Date, Battery Dates.
- **Battery System**: Capacity, RunTime, Temp, Status, Replacement Status, Actual Voltage, Current, Pack Counts, State of Health (SOH).
- **Input System**: Voltage, Frequency, Max/Min Voltage, Failure Reason, Last Transfer.
- **Output System**: Voltage, Load, Frequency, Current, Power (Watts), Apparent Power (VA), Energy (kWh).
- **Config**: High/Low Transfer Points, Shutdown Delays, Sensitivity.
- **Environment**: External Temp, Humidity, Probe Status.

## 2. Mikrotik Switch (MIB-II + Mikrotik Private)
Found in the 373KB raw walk:
- **System**: Name, Uptime, Contact, Location, OS Version, Serial Number.
- **Resource**: CPU Load, Total/Used RAM, Total/Used Disk, CPU Frequency, Active Fans, Voltage (V), Current (A).
- **Interface (Per Port)**: Name, Type, Speed, MTU, Admin/Oper Status, Last Change, Octets In/Out, Packets In/Out, Errors In/Out, Discards In/Out, Unicast/Multicast/Broadcast counters.
- **Wireless**: Client Counts, Frequency, TX/RX Rates, Signal Strength, Noise Floor.

## 3. Lenovo ThinkSystem (Full IPMI SDR)
All 250 sensors including:
- **Voltage**: 12V, 5V, 3.3V, CPU Vcore, DIMM Voltage, Battery Voltage.
- **Thermal**: Ambient, Exhaust, CPU1/2, DIMM 1-24, PCH, VRM.
- **Cooling**: Fan 1-12 Tach (Front/Rear).
- **Power**: Total Sys Watts, PSU 1/2 Input/Output, CPU Watts, Memory Watts.
- **Health**: Drive 0-7 Status, PSU 1/2 Presence, Chassis Intrusion.

## 4. Hikvision Security System (ISAPI HTTP XML)
- **Device**: Model, UUID, MAC, Firmware, Encoding Version, Location.
- **Status**: Device UpTime, Local Time, CPU Load %, Memory Usage %, Memory Avail.
- **Storage**: HDD ID, Name, Status (Full/Normal/Error), Total MB, Free MB.
- **Video**: Channel ID, Name, Res Width/Height, Codec (H265/H264), Bitrate Cap, Frame Rate.
- **Network**: IP, Subnet, Gateway, MTU, NTP Config, DNS Config.
- **Events**: Motion Detection Status, Recording Status, Alarm Inputs.
