# 33. PostgreSQL Query Reference — DCIM Database

**Versi Dokumen**: 1.0 | **Dibuat**: 2026-05-05  
**Database**: `dcim_sot` @ `192.168.101.73:5432`  
**User**: `sot_admin`

Dokumen ini berisi kumpulan query SQL yang dapat dijalankan langsung di **pgAdmin 4** untuk memantau dan mengaudit data dari seluruh jalur pipeline DCIM.

---

## 1. Ikhtisar Tabel per Jalur Data (Kategori: Server)

```
Pipeline DCIM — Server Data Flow:

Jalur Cepat (Telegraf → Kafka → Enrich):
  └─► dcim_events           [metric_name terisi, srv_disk_components = NULL]

Jalur Lambat (Redfish → server_redfish_to_pg.py):
  ├─► dcim_events           [srv_disk_components terisi, metric_name = NULL]
  ├─► dcim_server_disks     [Detail disk per slot]
  ├─► dcim_server_ram       [Detail RAM per slot]
  ├─► dcim_server_processors [Detail CPU per soket]
  └─► dcim_server_nics      [Detail NIC per port]

CMDB Source of Truth:
  └─► unified_assets        [Metadata CMDB: site, rack, status]
```

---

## 2. Query Diagnostik Jalur (Mana Data dari Jalur Mana?)

### 2.1 — Ringkasan volume data: Jalur Cepat vs. Jalur Lambat

```sql
-- ============================================================
-- QUERY 1: Perbandingan volume jalur cepat vs lambat
-- Untuk SEMUA server
-- ============================================================
SELECT
    CASE
        WHEN srv_disk_components IS NOT NULL THEN 'Jalur Lambat (HW Inventory)'
        ELSE 'Jalur Cepat (Metrik Realtime)'
    END AS jalur,
    COUNT(*)                         AS total_baris,
    COUNT(DISTINCT ip::text)         AS total_server_unik,
    MIN(event_time)                  AS data_tertua,
    MAX(event_time)                  AS data_terbaru
FROM dcim_events
WHERE device_type = 'server'
GROUP BY 1
ORDER BY 1;
```

**Hasil aktual (2026-05-04):**
| jalur | total_baris | total_server_unik | data_terbaru |
|:---|:---|:---|:---|
| Jalur Cepat (Metrik Realtime) | 49.568 | 55 perangkat | 2026-05-04 17:18 UTC |
| Jalur Lambat (HW Inventory) | 410 | 5 server | 2026-05-04 15:33 UTC |

---

## 3. Query per Perangkat (Contoh: SERVER-RENDER-02 / 10.50.0.6)

### 3.1 — Gabungan ringkasan satu server (kedua jalur)

```sql
-- ============================================================
-- QUERY 2: Semua data satu server, tampilkan jalur asalnya
-- Ganti '10.50.0.6' dengan IP server yang ingin dilihat
-- ============================================================
SELECT
    event_time,
    hostname,
    CASE
        WHEN srv_disk_components IS NOT NULL THEN '🔬 Jalur Lambat'
        ELSE '⚡ Jalur Cepat'
    END                                     AS jalur,
    metric_name,
    srv_firmware,
    srv_bios_version,
    enrichment_status,
    site,
    rack_name,
    (srv_disk_components IS NOT NULL)       AS has_disk_detail,
    (srv_cpu_components  IS NOT NULL)       AS has_cpu_detail,
    (srv_memory_components IS NOT NULL)     AS has_ram_detail,
    (srv_nic_components  IS NOT NULL)       AS has_nic_detail
FROM dcim_events
WHERE ip = '10.50.0.6'
ORDER BY event_time DESC
LIMIT 20;
```

### 3.2 — Hanya data jalur lambat (Hardware Inventory) satu server

```sql
-- ============================================================
-- QUERY 3: Snapshot hardware dari jalur lambat (satu server)
-- ============================================================
SELECT
    event_time,
    hostname,
    ip::text,
    srv_firmware         AS xcc_firmware,
    srv_bios_version     AS bios_version,
    srv_system_name,
    enrichment_status,
    site,
    rack_name,
    jsonb_array_length(srv_cpu_components::jsonb)    AS jumlah_cpu,
    jsonb_array_length(srv_memory_components::jsonb) AS jumlah_ram_slot,
    jsonb_array_length(srv_disk_components::jsonb)   AS jumlah_disk,
    jsonb_array_length(srv_nic_components::jsonb)    AS jumlah_nic
FROM dcim_events
WHERE ip = '10.50.0.6'
  AND srv_disk_components IS NOT NULL
ORDER BY event_time DESC
LIMIT 5;
```

### 3.3 — Hanya data jalur cepat (Metric Telemetry) satu server

```sql
-- ============================================================
-- QUERY 4: Metrik realtime dari jalur cepat (satu server)
-- ============================================================
SELECT
    event_time,
    hostname,
    metric_name,
    metric_value,
    metric_unit,
    severity,
    enrichment_status,
    site,
    rack_name
FROM dcim_events
WHERE ip = '10.50.0.6'
  AND srv_disk_components IS NULL
ORDER BY event_time DESC
LIMIT 20;
```

---

## 4. Query Tabel Komponen Hardware (Jalur Lambat)

> Semua tabel komponen di-refresh setiap kali `server_redfish_to_pg.py` berjalan (Daily 01:00). Data lama dihapus dan diganti snapshot terbaru.

### 4.1 — Detail Disk

```sql
-- ============================================================
-- QUERY 5: Semua disk per server
-- ============================================================
SELECT
    d.server_ip,
    e.hostname,
    d.slot,
    d.serial_number,
    d.model_name,
    d.size_gb,
    d.firmware_version
FROM dcim_server_disks d
JOIN (
    SELECT DISTINCT ON (ip::text) ip::text AS ip, hostname
    FROM dcim_events
    WHERE device_type = 'server' AND srv_disk_components IS NOT NULL
    ORDER BY ip::text, event_time DESC
) e ON e.ip = d.server_ip::text
ORDER BY d.server_ip, d.slot;
```

**Hasil aktual (SERVER-RENDER-02):**
| server_ip | hostname | slot | serial_number | model_name | size_gb | firmware_version |
|:---|:---|:---|:---|:---|:---|:---|
| 10.50.0.6 | SERVER-RENDER-02 | 1 | PHYI3403011G960CGN | 960GB 6Gbps SATA 2.5 SSD | 894 | 7CV1LR16 |
| 10.50.0.6 | SERVER-RENDER-02 | 2 | PHYI34020565960CGN | 960GB 6Gbps SATA 2.5 SSD | 894 | 7CV1LR16 |
| 10.50.0.6 | SERVER-RENDER-02 | 3 | PHYI340203NY960CGN | 960GB 6Gbps SATA 2.5 SSD | 894 | 7CV1LR16 |
| 10.50.0.6 | SERVER-RENDER-02 | Disk.0 | PHYI340203GS960CGN | 960GB 6Gbps SATA 2.5 SSD | 894 | 7CV1LR16 |

### 4.2 — Detail RAM

```sql
-- ============================================================
-- QUERY 6: Semua RAM per server + total kapasitas
-- ============================================================
SELECT
    server_ip,
    model_name                               AS vendor,
    COUNT(*)                                 AS jumlah_slot,
    SUM(size_mb)                             AS total_mb,
    ROUND(SUM(size_mb) / 1024.0, 0)         AS total_gb,
    MIN(speed_mhz)                           AS speed_mhz
FROM dcim_server_ram
GROUP BY server_ip, model_name
ORDER BY server_ip;
```

**Hasil aktual (SERVER-RENDER-02):**
| server_ip | vendor | jumlah_slot | total_mb | total_gb | speed_mhz |
|:---|:---|:---|:---|:---|:---|
| 10.50.0.6 | Samsung | 8 | 131.072 | 128 | 4800 |

### 4.3 — Detail CPU

```sql
-- ============================================================
-- QUERY 7: Semua CPU per server
-- ============================================================
SELECT
    server_ip,
    model_name,
    cores,
    logical_cores,
    speed_mhz,
    COUNT(*) AS jumlah_soket
FROM dcim_server_processors
GROUP BY server_ip, model_name, cores, logical_cores, speed_mhz
ORDER BY server_ip;
```

**Hasil aktual (SERVER-RENDER-02):**
| server_ip | model_name | cores | logical_cores | speed_mhz | jumlah_soket |
|:---|:---|:---|:---|:---|:---|
| 10.50.0.6 | AMD EPYC 9254 24-Core Processor | 24 | 48 | 4150 | 2 |

### 4.4 — Detail NIC

```sql
-- ============================================================
-- QUERY 8: Semua NIC per server
-- ============================================================
SELECT
    server_ip,
    label,
    mac_address,
    speed_gbps,
    model_name
FROM dcim_server_nics
ORDER BY server_ip, label;
```

**Hasil aktual (SERVER-RENDER-02):**
| server_ip | label | mac_address | speed_gbps | model_name |
|:---|:---|:---|:---|:---|
| 10.50.0.6 | NIC1 | 6C:FE:54:8C:FD:20 | 3 | External Ethernet Interface |
| 10.50.0.6 | NIC2 | 6C:FE:54:8C:FD:21 | 3 | External Ethernet Interface |
| 10.50.0.6 | NIC3 | 6C:FE:54:8C:FD:22 | 3 | External Ethernet Interface |
| 10.50.0.6 | NIC4 | 6C:FE:54:8C:FD:23 | 3 | External Ethernet Interface |

---

## 5. Query Audit Lengkap (Semua Server — Semua Tabel)

```sql
-- ============================================================
-- QUERY 9: Ringkasan inventaris semua server (jalur lambat)
-- Satu baris per server + total komponen
-- ============================================================
SELECT
    e.hostname,
    e.ip::text                 AS management_ip,
    e.site,
    e.rack_name,
    e.srv_firmware             AS xcc_firmware,
    e.srv_bios_version         AS bios,
    e.enrichment_status,
    p.jumlah_cpu,
    p.total_cores,
    r.jumlah_ram_slot,
    r.total_ram_gb,
    d.jumlah_disk,
    d.total_disk_gb,
    n.jumlah_nic,
    e.event_time               AS snapshot_time
FROM (
    SELECT DISTINCT ON (ip::text) *
    FROM dcim_events
    WHERE device_type = 'server' AND srv_disk_components IS NOT NULL
    ORDER BY ip::text, event_time DESC
) e
LEFT JOIN (
    SELECT server_ip, COUNT(*) AS jumlah_cpu, SUM(cores) AS total_cores
    FROM dcim_server_processors GROUP BY server_ip
) p ON p.server_ip = e.ip::text
LEFT JOIN (
    SELECT server_ip, COUNT(*) AS jumlah_ram_slot,
           ROUND(SUM(size_mb)/1024.0, 0) AS total_ram_gb
    FROM dcim_server_ram GROUP BY server_ip
) r ON r.server_ip = e.ip::text
LEFT JOIN (
    SELECT server_ip, COUNT(*) AS jumlah_disk, SUM(size_gb) AS total_disk_gb
    FROM dcim_server_disks GROUP BY server_ip
) d ON d.server_ip = e.ip::text
LEFT JOIN (
    SELECT server_ip, COUNT(*) AS jumlah_nic
    FROM dcim_server_nics GROUP BY server_ip
) n ON n.server_ip = e.ip::text
ORDER BY e.hostname;
```

---

## 6. Query Cek Kesehatan Tabel

```sql
-- ============================================================
-- QUERY 10: Cek apakah jalur lambat sudah berjalan hari ini
-- ============================================================
SELECT
    ip::text                             AS server_ip,
    hostname,
    MAX(event_time)                      AS last_hw_snapshot,
    NOW() - MAX(event_time)              AS usia_data,
    CASE
        WHEN MAX(event_time) > NOW() - INTERVAL '25 hours' THEN '✅ OK'
        WHEN MAX(event_time) > NOW() - INTERVAL '48 hours' THEN '⚠️ Terlambat'
        ELSE '🔴 STALE'
    END                                  AS status
FROM dcim_events
WHERE device_type = 'server'
  AND srv_disk_components IS NOT NULL
GROUP BY ip::text, hostname
ORDER BY last_hw_snapshot;
```

---

## 7. Query Gabungan (Fast Path & Slow Path Join)

Untuk menampilkan metrik suhu/daya (Jalur Cepat) bersamaan dengan versi firmware dan inventaris komponen (Jalur Lambat) dalam satu tabel, Anda harus melakukan JOIN antara data metrik terbaru dengan data *snapshot* terbaru per IP.

```sql
-- ============================================================
-- QUERY 11: FULL SENSOR & HARDWARE INVENTORY JOIN
-- Menggabungkan telemetri dinamis (reading_celsius, power_watts)
-- dengan status statis (srv_firmware, memory count).
-- Karena Telegraf memecah metrik per sensor ke baris yang berbeda,
-- kita harus mengambil nilai terbaru spesifik per sensor.
-- ============================================================
SELECT 
    e.hostname, 
    e.site,
    e.rack_name,
    s.srv_firmware,
    s.srv_bios_version,
    jsonb_array_length(s.srv_memory_components::jsonb) AS srv_memory_modules_count,
    
    -- Ambil Suhu Terbaru (Celsius)
    (SELECT raw_fields->>'reading_celsius' 
     FROM dcim_events 
     WHERE ip = e.ip AND device_type = 'server' AND raw_fields ? 'reading_celsius' 
     ORDER BY event_time DESC LIMIT 1) AS srv_reading_celsius,
     
    -- Ambil Beban Daya Terbaru (Watts)
    (SELECT raw_fields->>'power_output_watts' 
     FROM dcim_events 
     WHERE ip = e.ip AND device_type = 'server' AND raw_fields ? 'power_output_watts' 
     ORDER BY event_time DESC LIMIT 1) AS srv_power_watts

FROM (
    -- Dapatkan daftar unik semua server
    SELECT DISTINCT ON (ip::text) ip, hostname, site, rack_name
    FROM dcim_events 
    WHERE device_type = 'server'
) e
LEFT JOIN (
    -- Ambil baris snapshot hardware TERBARU per IP
    SELECT DISTINCT ON (ip::text) * 
    FROM dcim_events 
    WHERE device_type = 'server' AND srv_disk_components IS NOT NULL
    ORDER BY ip::text, event_time DESC
) s ON e.ip::text = s.ip::text
ORDER BY e.hostname 
LIMIT 10;
```

---

```sql
-- ============================================================
-- QUERY 12: MASTER SERVER VIEW (Advanced Component Aggregation)
-- Query ini tidak menampilkan raw JSON sama sekali, melainkan 
-- melakukan kalkulasi agregat. Menampilkan metrik utama beserta:
-- Jumlah soket CPU, total cores/threads, total kapasitas RAM (GB),
-- dan ringkasan tipe disk beserta kuantitasnya per tipe.
-- ============================================================
SELECT 
    e.hostname,
    (SELECT raw_fields->>'reading_celsius' FROM dcim_events WHERE ip = e.ip AND device_type = 'server' AND raw_fields ? 'reading_celsius' ORDER BY event_time DESC LIMIT 1) AS temp_c,
    (SELECT raw_fields->>'power_output_watts' FROM dcim_events WHERE ip = e.ip AND device_type = 'server' AND raw_fields ? 'power_output_watts' ORDER BY event_time DESC LIMIT 1) AS power_w,
    p.jumlah_socket_cpu,
    p.total_cores,
    p.total_threads,
    r.jumlah_modul_ram,
    r.total_ram_gb,
    d.jumlah_tipe_disk,
    d.ringkasan_tipe_disk
FROM (
    SELECT DISTINCT ON (ip::text) ip, hostname
    FROM dcim_events 
    WHERE device_type = 'server'
) e
LEFT JOIN (
    SELECT server_ip::text, COUNT(*) AS jumlah_socket_cpu, SUM(cores) AS total_cores, SUM(logical_cores) AS total_threads 
    FROM dcim_server_processors GROUP BY server_ip::text
) p ON p.server_ip = e.ip::text
LEFT JOIN (
    SELECT server_ip::text, COUNT(*) AS jumlah_modul_ram, ROUND(SUM(size_mb)/1024.0, 0) AS total_ram_gb 
    FROM dcim_server_ram GROUP BY server_ip::text
) r ON r.server_ip = e.ip::text
LEFT JOIN (
    SELECT server_ip::text, COUNT(*) AS jumlah_tipe_disk, STRING_AGG(disk_group, ' | ') AS ringkasan_tipe_disk
    FROM (
        SELECT server_ip::text, model_name || ' (' || COUNT(*) || ' unit)' AS disk_group
        FROM dcim_server_disks
        GROUP BY server_ip::text, model_name
    ) sub GROUP BY server_ip
) d ON d.server_ip = e.ip::text
ORDER BY e.hostname;
```

---

*Referensi terkait:*
- *Arsitektur pipeline: `docs/19-kafka-pipeline-architecture.md`*
- *Capabilities Ralph sync: `docs/29-ralph-auto-update-capabilities.md`*
- *Skrip pengambilan data: `scripts/server_redfish_to_pg.py`*
