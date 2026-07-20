# Implementation Plan: Metric Gap — Memperbanyak Metric Names di TimescaleDB

> **Tanggal**: 2026-07-20  
> **Server**: srv-rnd-dcim (10.70.0.56)  
> **Prioritas**: P1 — diperlukan Tim AI untuk anomaly detection & RCA  
> **Status**: 📋 Implementation Plan (belum eksekusi)  
> **Referensi**: `docs/handoff/2026-07-19-ralph-asset_id-implementation-handoff.md`

---

## Problem Statement

Tim AI melaporkan:

> *"anomaly & RCA udah real, sisanya masih synthetic karena data di DB belum lengkap. Energy paling parah — metric names yang di-query (total_facility_power, it_equipment_power) bahkan nggak exist di tabel metrics."*

**Verifikasi**: Benar. Saat ini TimescaleDB hanya memiliki **5 metric names** dari 6 device types, padahal puluhan metric tersedia di raw data pipeline.

---

## 1. Current State

### 1.1 Metrics yang Sudah Masuk TimescaleDB (5 metric names)

| Metric Name | Source Device | 24h Volume | Kategori |
|-------------|:---:|:---:|-----|
| `interface_status` | network, nas | 92,672 | Network/NAS connectivity |
| `disk_temperature` | nas | 25,868 | NAS thermal |
| `status_online` | cctv, nvr | 5,312 | CCTV availability |
| `cpu_utilization` | server | 2,423 | Server compute |
| `battery_capacity` | ups | 921 | UPS power |

### 1.2 Metrics yang TERSEDIA di Raw Data tapi DIBUANG (guesstimate dari raw samples)

| Device | Raw Fields Tersedia | Masuk TSDB | Dibuang | Status |
|--------|:---:|:---:|:---:|---|
| **UPS** | 20+ numeric fields | 1 (`battery_capacity`) | 19+ | 🔴 Critical |
| **NAS** | 10+ numeric fields | 2 (`disk_temperature`, `interface_status`) | 8+ | 🟠 |
| **Server** | 5+ numeric fields | 1 (`cpu_utilization`) | 4+ | 🟠 |
| **CCTV** | 5 numeric fields | 1 (`status_online`) | 4 | 🟡 |
| **Network** | 15+ numeric fields | 1 (`interface_status`) | 14+ | 🟠 |
| **NVR** | 5 numeric fields | 1 (`status_online`) | 4 | 🟡 |

### 1.3 Tim AI Requirements (dari anomaly & energy model)

| Metric Name | Kebutuhan AI | Ada di TSDB? | Prioritas |
|-------------|:---:|:---:|:---|
| `total_facility_power` | Energy optimization | ❌ | P1 |
| `it_equipment_power` | Energy optimization | ❌ | P1 |
| `battery_temperature` | UPS anomaly | ❌ | P1 |
| `output_voltage` | UPS anomaly | ❌ | P1 |
| `output_load` | UPS capacity | ❌ | P1 |
| `memory_utilization` | Server capacity | ❌ | P2 |
| `disk_utilization` / `volume_usage` | NAS capacity | ❌ | P2 |
| `cpu_load` (switch) | Network anomaly | ❌ | P2 |
| `memory_usage_pct` | CCTV anomaly | ❌ | P2 |
| `temperature` (server) | Server thermal | ❌ | P2 |

---

## 2. Root Cause Analysis

### Root Cause 1: `secondary_metrics` didefinisikan tapi tidak diproses

**File**: `src/skills/telemetry/normalizer/executor.py`  
**Fungsi**: `resolve_metric()` hanya mengembalikan **1 metric per raw message**.  
**Config**: `configs/metric_mapping.json` mendefinisikan `secondary_metrics` array di beberapa entry tapi tidak ada kode yang membacanya.

```json
// metric_mapping.json — secondary_metrics DIDEKLARASI:
"ups_apc": {
    "metric_name": "battery_capacity",      // ← hanya ini yang diproses
    "metric_field": "battery_capacity",
    "secondary_metrics": [
        {"field": "battery_temp",   "name": "battery_temperature"},  // ← diabaikan
        {"field": "output_voltage", "name": "output_voltage"}        // ← diabaikan
    ]
}
```

```python
# executor.py — secondary_metrics TIDAK PERNAH DIBACA:
def resolve_metric(raw_message):
    metric_name = mapping.get("metric_name", "general_metric")
    # ... ambil metric_field, return (metric_name, value, unit, severity)
    # ← TIDAK ADA LOOP untuk secondary_metrics
```

### Root Cause 2: `server_redfish` measurement TIDAK PUNYA mapping

Raw data dari `dcim.raw.hardware.server` dengan measurement `server_redfish` hanya menghasilkan 1 field (`power_state`) karena tidak ada mapping di `metric_mapping.json`.

### Root Cause 3: Computed metrics tidak ada

`total_facility_power` dan `it_equipment_power` adalah **computed fields** — perlu perhitungan dari existing raw data:
- `total_facility_power` ≈ `output_voltage × output_current` dari UPS
- `it_equipment_power` ≈ sum power consumption dari semua server (Redfish)

---

## 3. Implementation Plan

### Phase 1: Enable `secondary_metrics` Processing (estimasi: 1 jam)

**File**: `src/skills/telemetry/normalizer/executor.py`

**Perubahan**:
1. Modifikasi `resolve_metric()` → kembalikan **list of metrics**, bukan single metric
2. Modifikasi `process_message()` → loop per metric dan produce N event untuk 1 raw message
3. Setiap secondary metric menjadi Kafka event sendiri (bisa dibedakan via `metric_name`)

**Struktur baru**:

```python
def resolve_metrics(raw_message):
    """Return list of (metric_name, metric_value, metric_unit, severity) tuples."""
    results = []
    # Primary metric
    metric_name = mapping.get("metric_name", "general_metric")
    # ... existing logic ...
    results.append((metric_name, metric_value, metric_unit, severity))
    
    # NEW: Secondary metrics
    for sec in mapping.get("secondary_metrics", []):
        field = sec.get("field")
        name = sec.get("name")
        unit = sec.get("unit", "")
        if field and name and field in fields:
            value = fields[field]
            if value is not None:
                results.append((name, value, unit, "info"))
    return results
```

**Metrics yang akan muncul**:

| Measurement | Metric Baru | Sumber Field |
|-------------|------------|-------------|
| `ups_apc` | `battery_temperature` | `battery_temp` |
| `ups_apc` | `output_voltage` | `output_voltage` |
| `cctv_metrics` | `cpu_utilization` | `cpuUtilization` |
| `cctv_metrics` | `memory_usage` | `memoryUsage` |
| `cctv_metrics` | `memory_usage_pct` | `memoryUsagePct` |
| `server_redfish_util` | `memory_utilization` | `memoryUsage` |

### Phase 2: Add `server_redfish` Mapping (estimasi: 30 min)

**File**: `configs/metric_mapping.json`

**Perubahan**: Tambah entry baru untuk measurement `server_redfish` (thermal, power, health dari Redfish API):

```json
"server_redfish": {
    "metric_name": "power_state",
    "metric_field": "power_state",
    "metric_unit": "status_code",
    "secondary_metrics": [
        {"field": "temperature_celsius", "name": "system_temperature", "unit": "celsius"},
        {"field": "fan_speed_rpm", "name": "fan_speed", "unit": "rpm"},
        {"field": "power_output_watts", "name": "power_consumption", "unit": "watts"},
        {"field": "health_status", "name": "health_status", "unit": "status_code"}
    ]
}
```

> **Note**: Field names asli dari raw data perlu diverifikasi. Lihat sample di Kafka topic `dcim.raw.hardware.server` untuk field name yang tepat (case-sensitive).

### Phase 3: Add Computed Energy Metrics (estimasi: 1.5 jam)

**File**: `src/skills/telemetry/normalizer/executor.py`

**Perubahan**: Tambah bagian computed metrics di `process_message()` setelah existing logic:

```python
# After existing UPS max_load computation, add:
if device_type == "ups":
    # Computed: total_facility_power (watts)
    try:
        voltage = float(fields.get("output_voltage") or 0)
        current = float(fields.get("output_current") or 0)
        load_pct = float(fields.get("output_load") or 0)
        if voltage > 0 and current > 0:
            total_power = voltage * current
            computed_metrics.append(("total_facility_power", total_power, "watts", "info"))
        if voltage > 0 and load_pct > 0:
            it_power = voltage * (current * load_pct / 100.0)
            computed_metrics.append(("it_equipment_power", it_power, "watts", "info"))
    except: pass

if device_type == "server":
    # Computed: it_equipment_power from Redfish power_output_watts
    power = fields.get("power_output_watts")
    if power:
        computed_metrics.append(("it_equipment_power", float(power), "watts", "info"))
```

> **Note**: Rumus power perlu divalidasi dengan Tim AI — pastikan unit sesuai (watt vs kW).

### Phase 4: Add Network Metrics Mapping (estimasi: 30 min)

**File**: `configs/metric_mapping.json`

**Perubahan**: Tambah entry untuk MikroTik SNMP metrics:

```json
"mikrotik_snmp": {
    "metric_name": "cpu_load",
    "metric_field": "cpu_load",
    "metric_unit": "percent",
    "secondary_metrics": [
        {"field": "memory_used", "name": "memory_used", "unit": "bytes"},
        {"field": "memory_total", "name": "memory_total", "unit": "bytes"},
        {"field": "uptime_seconds", "name": "uptime", "unit": "seconds"},
        {"field": "temperature", "name": "system_temperature", "unit": "celsius"}
    ]
}
```

### Phase 5: Add NAS Volume/Storage Metrics (estimasi: 30 min)

**File**: `configs/metric_mapping.json`

**Perubahan**: Perluas mapping `dcim_nas` dengan secondary metrics:

```json
"dcim_nas": {
    "metric_name": "disk_temperature",
    "metric_field": "diskTemp",
    "metric_unit": "celsius",
    "secondary_metrics": [
        {"field": "volumeUsedBytes", "name": "volume_used", "unit": "bytes"},
        {"field": "volumeTotalBytes", "name": "volume_total", "unit": "bytes"}, 
        {"field": "volumeUsagePct", "name": "volume_usage_pct", "unit": "percent"},
        {"field": "diskStatus", "name": "disk_health", "unit": "status_code"}
    ]
}
```

### Phase 6: Restart & Verify (estimasi: 30 min)

```bash
# 1. Backup current config
cp configs/metric_mapping.json configs/metric_mapping.json.bak.$(date +%Y%m%d)

# 2. Restart normalizer
sudo systemctl restart dcim-normalizer

# 3. Wait 2 minutes then verify
sleep 120
docker exec dcim-timescaledb psql -U analytics_user -d dcim_analytics \
  -c "SELECT metric_name, count(DISTINCT source) as sources, count(*) as cnt 
      FROM metrics WHERE time > NOW() - INTERVAL '5 minutes' 
      GROUP BY metric_name ORDER BY cnt DESC;"

# 4. Expected: 15+ distinct metric names (up from 5)

# 5. Verify AI team metrics exist
docker exec dcim-timescaledb psql -U analytics_user -d dcim_analytics \
  -c "SELECT count(*) FROM metrics 
      WHERE metric_name IN ('total_facility_power','it_equipment_power') 
      AND time > NOW() - INTERVAL '5 minutes';"
```

### Phase 7: Commit (estimasi: 15 min)

```bash
git add src/skills/telemetry/normalizer/executor.py configs/metric_mapping.json
git commit -m "feat: enable secondary_metrics processing + add computed power metrics

Phase 1: process_message() now emits all secondary_metrics from config
Phase 2: Added server_redfish measurement mapping (thermal, power, fan, health)
Phase 3: Added computed total_facility_power & it_equipment_power from UPS
Phase 4: Added network SNMP metrics (cpu, memory, uptime, temperature)
Phase 5: Added NAS volume/storage secondary metrics

Result: TimescaleDB metric names grow from 5 → ~25 distinct metrics
        including total_facility_power & it_equipment_power for AI energy model"
git push origin main
```

---

## 4. Summary — Expected Result

| Fase | Metric Baru | Jumlah |
|:---:|---|:---:|
| 1 | `battery_temperature`, `output_voltage`, `memory_usage`, `memory_usage_pct`, `memory_utilization` | 5 |
| 2 | `system_temperature`, `fan_speed`, `power_consumption`, `health_status` | 4 |
| 3 | `total_facility_power`, `it_equipment_power` | 2 |
| 4 | `cpu_load`, `memory_used`, `memory_total`, `uptime` | 4 |
| 5 | `volume_used`, `volume_total`, `volume_usage_pct`, `disk_health` | 4 |
| **TOTAL** | | **~19 metric baru** |

**Final state**: ~24 metric names (dari sebelumnya 5), mencakup semua 6 device types dengan metrik yang dibutuhkan Tim AI untuk anomaly detection, RCA, dan energy optimization.

---

## 5. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|:---:|-----|
| Secondary metrics spike Kafka throughput | Medium | Batch produce dengan limit, atau filter metric dengan nilai null |
| Field name mismatch di raw data | Medium | Phase 2-5: verifikasi dulu field names dari Kafka topic sample |
| Computed power formula salah | Low | Validasi dengan Tim AI — formula bisa diadjust nanti |
| `metric_mapping.json` schema break | Low | Schema tidak strict, field baru bersifat additive |
| TimescaleDB hypertable load | Low | INSERT rate same, hanya metric_name berbeda |

---

## 6. Quick Reference

```bash
# Lihat metric names terkini
docker exec dcim-timescaledb psql -U analytics_user -d dcim_analytics \
  -c "SELECT metric_name, source, count(*) FROM metrics 
      WHERE time > NOW() - INTERVAL '1 hour' 
      GROUP BY 1,2 ORDER BY 3 DESC;"

# Cek raw data field names untuk verifikasi
# UPS:
kafka-console-consumer --bootstrap-server localhost:9094 --topic dcim.raw.power.ups \
  --consumer.config client-ssl.properties --max-messages 1 | python3 -m json.tool
# Server:
kafka-console-consumer --bootstrap-server localhost:9094 --topic dcim.raw.hardware.server \
  --consumer.config client-ssl.properties --max-messages 1 | python3 -m json.tool
```

---

*Dokumen ini adalah implementation plan — belum ada kode yang diubah.  
Agent berikutnya silakan mulai dari Phase 1 setelah verifikasi ulang kondisi pipeline.*
