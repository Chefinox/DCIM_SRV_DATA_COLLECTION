# Skill: Redfish Scanner

## Purpose
Melakukan pemindaian mendalam (deep scan) pada server fisik melalui protokol Redfish (BMC) untuk mengumpulkan inventori hardware secara lengkap dan akurat.

## Capabilities
- Mengambil informasi sistem (Serial Number, Model, BIOS).
- Mengidentifikasi komponen CPU (Cores, Speed).
- Inventori RAM (Capacity, Speed, Slot).
- Inventori Storage (Model, SN, Size, Slot/Physical Location).
- Inventori NIC (MAC Address, Speed).
- Melakukan normalisasi format slot disk.

## Inputs
- `ip`: IP Management/BMC server.
- `user`: Username Redfish.
- `password`: Password Redfish.

## Outputs
- Menyimpan snapshot historis ke `dcim_events`.
- Sinkronisasi tabel komponen (`dcim_server_disks`, `dcim_server_ram`, dll).
- Mengembalikan dictionary hasil scan yang sudah diperkaya (enriched).

## Dependencies
- **Tools**: `RedfishClient`, `PostgresClient`.
- **Schemas**: `ServerInventoryTransformer`, `AssetMetadataTransformer`.

## Execution Flow
1. Inisialisasi koneksi Redfish.
2. Pengambilan data mentah dari endpoint `/Systems`, `/Chassis`, `/Managers`, `/Memory`, `/Storage`.
3. Transformasi data mentah ke skema DCIM internal.
4. Pengayaan data melalui lookup ke `unified_assets` (PostgreSQL).
5. Persistensi data ke tabel-tabel terkait di PostgreSQL.
