# Telegraf Redfish Discovery Logic (Server Monitoring)

## 📋 Overview

Unlike the APC UPS and MikroTik switches which use **SNMP** (requires manual OID mapping), your Lenovo ThinkSystem servers use **Redfish**.

Redfish is a modern, RESTful API (REST + JSON) managed by the server's BMC (XClarity Controller). Because it is standardized, Telegraf can automatically "discover" every sensor on a server without being given a list of parameters.

---

## 🔍 Discovery Mechanism

When the Telegraf service starts, the `[[inputs.redfish]]` plugin performs the following steps:

### 1. The Entry Point
Telegraf connects to the server management IP and hits the root API:
`https://{IP}/redfish/v1/`

### 2. Resource Crawling
The plugin then automatically crawls (follows links) to the three most critical hardware resources:

| Resource Path | Data Discovered |
| :--- | :--- |
| `/redfish/v1/Chassis/{id}/Thermal` | **Temperatures:** Ambient, CPU, DIMM, etc. <br> **Fans:** RPM for every chassis fan. |
| `/redfish/v1/Chassis/{id}/Power` | **PSUs:** Input/Output wattage, voltage. <br> **Control:** Power limit settings. |
| `/redfish/v1/Systems/{id}` | **System:** CPU core counts, Memory size, Health. |

### 3. Metric Mapping (JSON to Elasticsearch)
The plugin converts the Redfish JSON properties into Telegraf fields automatically:

| Redfish JSON Property | Telegraf Field Path |
| :--- | :--- |
| `ReadingCelsius` | `server_redfish.reading_celsius` |
| `Reading` (within Fans) | `server_redfish.reading_rpm` |
| `PowerOutputWatts` | `server_redfish.power_output_watts` |
| `Status.Health` | `tag.health` |

---

## ⚙️ Configuration Simplicity

Because the discovery is automatic, your `servers-redfish.conf` is extremely minimal. 

**All you need is:**
1.  **Management IP** (`address`)
2.  **Credentials** (`hndept`)
3.  **Name Override** (Used to group them in ES)

**You do NOT need:**
*   A list of fan names (they are found automatically).
*   A list of temperature thresholds (they are read via the API).
*   Unique OIDs for each server model.

---

## 🛠️ Customizing the Parameters (Filtering)

While crawling is automatic, you can use **Global Filters** to choose exactly which metrics are stored in Elasticsearch. Add these lines to your `servers-redfish.conf` below the login credentials if you want to limit the data.

### Option A: `fieldpass` (Include Only)
Use this if you only want specific metrics (e.g. Temperature and Power only):
```toml
# ONLY keep these metrics, discard the rest (like Fans)
fieldpass = ["power_output_watts", "reading_celsius"]
```

### Option B: `fielddrop` (Exclude Only)
Use this to remove noisy data that you don't need:
```toml
# Automatically find everything EXCEPT Fan speeds
fielddrop = ["reading_rpm"]
```

### Option C: `tagpass` (Filter by Sensor Name)
Use this to monitor specific hardware (e.g., ONLY the CPU temperatures):
```toml
# Only keep documents where the sensor name is "CPU 1 Temp"
[inputs.redfish.tagpass]
  name = ["CPU 1 Temp"]
```

---

## 🔒 Strict "Manual-Style" Mode

If you wish to avoid the automatic discovery of "extra" sensors and want to behave like the manual SNMP (OID-based) method, you can use a **Strict Field List**. 

In this mode, Telegraf still crawls the server, but it **immediately discards** anything that is not on your chosen list.

### Example: Locked-Down Configuration
```toml
[[inputs.redfish]]
  address = "https://10.50.0.5"
  # ... login info ...
  
  # --- MANUAL PARAMETER LIST ---
  # Only these specific metrics will reach Elasticsearch
  fieldpass = [
    "reading_celsius",       # Temperatures
    "reading_rpm",           # Fan Speeds
    "power_output_watts",    # PSU Output
    "power_input_watts",     # PSU Input
    "line_input_voltage"     # AC Voltage
  ]

  # Further restrict to ONLY the main board sensors
  [inputs.redfish.tagpass]
    name = ["CPU 1 Temp", "CPU 2 Temp", "Ambient Temp"]
```

**Benefits of this mode:**
1.  **Predictability:** Your Elasticsearch schema will only contain exactly what you listed.
2.  **Storage Efficiency:** Prevents hundreds of "extra" sensor readings from filling up your disk.
3.  **Auditing:** You have a clear list in your config of exactly what is being monitored.

---

## 💡 Troubleshooting
If a metric is missing in Elasticsearch:
1.  **Check Redfish availability:** Run `curl -k https://{IP}/redfish/v1/Chassis/1/Thermal`.
2.  **Verify Plugin Connection:** The plugin requires HTTPS. Check for SSL certificate errors in `telegraf.log`.
3.  **Automatic Naming:** Remember that sensors are tagged with `tag.name`. Use this in Kibana Discover to find your specific sensor (e.g., `"CPU 1 Temp"`).
