# Skill: Asset Enricher

## Purpose
Memperkaya data inventori teknis dengan metadata kontekstual dari CMDB (Single Source of Truth).

## Capabilities
- Melakukan lookup ke tabel `unified_assets` berdasarkan Serial Number atau Hostname.
- Mengidentifikasi Site, Rack, Room, dan Status Asset.
- Mendeteksi Environment (Production/Staging) dan Business Unit.
- Menggunakan `AssetMetadataTransformer` untuk normalisasi data vendor (Netbox/Ralph).

## Inputs
- `inventory_data`: Dictionary yang minimal berisi `serial_number` atau `hostname`.

## Outputs
- `enriched_data`: Dictionary input yang telah ditambahkan field-field CMDB.

## Dependencies
- **Tools**: `PostgresClient`.
- **Schemas**: `AssetMetadataTransformer`.

## Execution Flow
1. Menerima data inventori mentah.
2. Melakukan query SQL ke SOT database.
3. Mentransformasikan `raw_payload` (JSON) menjadi field-field standar.
4. Menggabungkan hasil pengayaan ke objek original.
