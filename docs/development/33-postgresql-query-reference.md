# 33. PostgreSQL Query Reference — DCIM Database

**Versi Dokumen**: 1.2 (Hybrid Path Architecture) | **Terakhir Diperbarui**: 2026-05-07  
**Database**: `dcim_sot` @ `192.168.101.73:5432`

Dokumen ini menjelaskan cara mengambil data dari dua jalur arsitektur DCIM yang berbeda dan menyediakan kueri audit per kategori perangkat.

---

## 1. Konsep Arsitektur: Jalur Cepat vs. Jalur Lambat

Untuk memahami data di `dcim_events`, Anda harus membedakan asal datanya:

| Fitur | ⚡ Jalur Cepat (Fast Path) | 🐢 Jalur Lambat (Slow Path) |
| :--- | :--- | :--- |
| **Sumber** | Telegraf → Kafka → Normalizer | `server_redfish_to_pg.py` (Redfish API) |
| **Frekuensi** | Real-time (10 detik - 1 menit) | Periodik (Harian / Per jam) |
| **Konten** | Metrik Dinamis (Suhu, Watt, RPM, Voltase) | Inventaris Statis (CPU Cores, RAM SN, Disk SN, FW) |
| **Kategori** | Semua (Server, UPS, NAS, Network) | Khusus Server & Storage Storage |

---

## 2. Kueri Kategori: SERVER (Jalur Hybrid)

Server adalah satu-satunya kategori yang menggabungkan kedua jalur. Gunakan kueri ini untuk melihat data telemetri (Cepat) dan inventaris (Lambat) sekaligus.

```sql
-- ============================================================
-- QUERY 1: Server Master View (Join Fast & Slow Path)
-- Menampilkan data hardware terbaru beserta metrik suhu terakhir.
-- ============================================================
SELECT 
    s.hostname,
    s.ip,
    s.srv_firmware AS xcc_fw,
    s.srv_bios_version AS bios,
    -- Komponen dari Jalur Lambat
    jsonb_array_length(s.srv_cpu_components::jsonb) AS cpu_sockets,
    jsonb_array_length(s.srv_memory_components::jsonb) AS ram_slots,
    jsonb_array_length(s.srv_disk_components::jsonb) AS disk_count,
    -- Metrik terbaru dari Jalur Cepat
    (SELECT srv_reading_celsius FROM dcim_events 
     WHERE ip = s.ip AND srv_reading_celsius IS NOT NULL 
     ORDER BY event_time DESC LIMIT 1) AS last_temp_c,
    (SELECT srv_power_watts FROM dcim_events 
     WHERE ip = s.ip AND srv_power_watts IS NOT NULL 
     ORDER BY event_time DESC LIMIT 1) AS last_power_w
FROM (
    SELECT DISTINCT ON (ip::text) * 
    FROM dcim_events 
    WHERE device_type = 'server' AND srv_disk_components IS NOT NULL
    ORDER BY ip::text, event_time DESC
) s
ORDER BY s.hostname;
```

---

## 3. Kueri Kategori: UPS (Jalur Cepat)

UPS hanya menggunakan Jalur Cepat (SNMP via Telegraf). Seluruh datanya adalah telemetri real-time.

```sql
-- ============================================================
-- QUERY 2: UPS Real-time Monitoring
-- ============================================================
SELECT 
    event_time,
    hostname,
    ups_battery_capacity AS batt_pct,
    ups_battery_runtime AS runtime_min,
    ups_output_load AS load_pct,
    ups_input_voltage AS v_in,
    ups_output_voltage AS v_out,
    ups_battery_status AS status_code -- 2=Normal, 3=Low, etc.
FROM dcim_events 
WHERE device_type = 'ups'
ORDER BY event_time DESC LIMIT 20;
```

---

## 4. Kueri Kategori: NAS (Jalur Hybrid Ringan)

NAS menggunakan SNMP untuk metrik cepat dan status disk.

```sql
-- ============================================================
-- QUERY 3: NAS Storage & Health
-- ============================================================
SELECT 
    event_time,
    hostname,
    manufacturer,
    model,
    nas_system_temp AS sys_temp,
    nas_disk_temp AS disk_temp,
    nas_disk_status AS disk_health -- 1=Normal, 2=Initialized, etc.
FROM dcim_events 
WHERE device_type = 'nas'
ORDER BY event_time DESC LIMIT 20;
```

---

## 5. Kueri Kategori: NETWORK (Jalur Cepat)

Memantau beban interface switch. Data ini bersifat volatil (berubah sangat cepat).

```sql
-- ============================================================
-- QUERY 4: Switch Traffic & Port Status
-- ============================================================
SELECT 
    event_time,
    hostname,
    net_if_name AS port,
    net_if_oper_status AS status, -- 1=Up, 2=Down
    net_if_speed / 1000000 AS speed_mbps,
    net_if_in_octets AS rx_bytes,
    net_if_out_octets AS tx_bytes
FROM dcim_events 
WHERE device_type = 'network_switch' AND net_if_name IS NOT NULL
ORDER BY event_time DESC LIMIT 50;
```

---

## 6. Kueri Kategori: CCTV & NVR (Jalur Identitas)

Fokus pada ketersediaan perangkat dan identitas model di Back Office.

```sql
-- ============================================================
-- QUERY 5: CCTV Back-Office Inventory
-- ============================================================
SELECT 
    event_time,
    hostname,
    ip,
    serial_number,
    COALESCE(raw_tags->>'model', 'N/A') AS model,
    COALESCE(raw_tags->>'firmware', 'N/A') AS firmware,
    site,
    environment
FROM dcim_events 
WHERE device_type IN ('cctv', 'nvr')
ORDER BY event_time DESC LIMIT 20;
```

---

## 7. Query Audit Jalur (Debugging)

Gunakan ini untuk memastikan Jalur Lambat (Redfish) masih aktif mengirim data harian.

```sql
-- ============================================================
-- QUERY 6: Audit Usia Data Jalur Lambat
-- ============================================================
SELECT
    hostname,
    MAX(event_time) AS last_snapshot,
    NOW() - MAX(event_time) AS usia_data,
    CASE 
        WHEN MAX(event_time) > NOW() - INTERVAL '25 hours' THEN '✅ AKTIF'
        ELSE '🔴 TERLAMBAT/MATI'
    END AS status_jalur_lambat
FROM dcim_events
WHERE device_type = 'server' AND srv_disk_components IS NOT NULL
GROUP BY hostname
ORDER BY last_snapshot DESC;
```

---
*Dokumentasi Terkait:*
- *Alur Pipeline: `docs/19-kafka-pipeline-architecture.md`*
- *Sync Ralph: `docs/29-ralph-auto-update-capabilities.md`*
