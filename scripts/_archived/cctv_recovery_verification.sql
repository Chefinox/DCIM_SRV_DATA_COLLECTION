-- ============================================================================
-- CCTV Recovery: SQL Verification & Validation Scripts
-- For Ralph PostgreSQL Database Administrator
-- Date: 2026-05-12
-- ============================================================================

-- Context: 21 CCTV assets hilang dari Ralph database setelah migrasi gagal
-- Purpose: Verify current state dan validate setelah re-registration

-- ============================================================================
-- SECTION 1: PRE-IMPORT VERIFICATION
-- ============================================================================

-- 1.1 Check current CCTV count in Ralph
SELECT 
    COUNT(*) as total_hikvision_assets,
    COUNT(DISTINCT sn) as unique_serial_numbers
FROM assets_datacenterasset
WHERE manufacturer_id IN (
    SELECT id FROM assets_manufacturer WHERE name = 'Hikvision'
);
-- Expected: ~10 assets (yang berhasil ter-recover)

-- 1.2 List existing CCTVs
SELECT 
    id,
    hostname,
    sn as serial_number,
    model_id,
    status,
    service_env_id,
    created,
    modified
FROM assets_datacenterasset
WHERE manufacturer_id IN (
    SELECT id FROM assets_manufacturer WHERE name = 'Hikvision'
)
ORDER BY hostname;

-- 1.3 Check if required references exist
-- Manufacturer
SELECT id, name FROM assets_manufacturer WHERE name = 'Hikvision';
-- Should return 1 row

-- Service Environment
SELECT id, name FROM assets_serviceenvironment WHERE name LIKE '%Back Office%';
-- Should return 1 row (or create if not exists)

-- Models
SELECT id, name FROM assets_assetmodel 
WHERE name IN (
    'DS-2CD1121-I',
    'DS-2CD1043G0E-I',
    'DS-2CD1143G0E-I',
    'DS-2CD1021-I',
    'DS-2CD3121G0-I'
);
-- Should return 5 rows (or create if not exists)

-- ============================================================================
-- SECTION 2: MISSING SERIAL NUMBERS CHECK
-- ============================================================================

-- 2.1 List of 21 missing serial numbers
WITH missing_sns AS (
    SELECT unnest(ARRAY[
        'DS-2CD1043G0E-I20200427AAWRE30076984',
        'DS-2CD1121-I20200308AAWRE17568965',
        'DS-2CD1121-I20200308AAWRE17568450',
        'DS-2CD1121-I20200308AAWRE17568469',
        'DS-2CD1043G0E-I20200427AAWRE30076719',
        'DS-2CD1121-I20200308AAWRE17568933',
        'DS-2CD1143G0E-I20210227AAWRF58406256',
        'DS-2CD1121-I20200308AAWRE17568170',
        'DS-2CD1143G0E-I20210227AAWRF58406296',
        'DS-2CD1021-I20201119AAWRE99707505',
        'DS-2CD1121-I20200308AAWRE17568951',
        'DS-2CD1121-I20200308AAWRE17568954',
        'DS-2CD1121-I20200308AAWRE17568952',
        'DS-2CD1121-I20200308AAWRE17568968',
        'DS-2CD1121-I20200308AAWRE17568966',
        'DS-2CD1121-I20200308AAWRE17568967',
        'DS-2CD1121-I20200308AAWRE17568953',
        'DS-2CD1121-I20200308AAWRE17568949',
        'DS-2CD1121-I20200308AAWRE17568950',
        'DS-2CD1121-I20200308AAWRE17568948',
        'DS-2CD3121G0-I20200427AAWRE30076984'
    ]) AS sn
)
SELECT 
    m.sn,
    CASE 
        WHEN a.sn IS NOT NULL THEN '✓ EXISTS'
        ELSE '✗ MISSING'
    END as status
FROM missing_sns m
LEFT JOIN assets_datacenterasset a ON m.sn = a.sn
ORDER BY status, m.sn;
-- Should show 21 rows with '✗ MISSING' status

-- ============================================================================
-- SECTION 3: POST-IMPORT VERIFICATION
-- ============================================================================

-- 3.1 Verify total count after import
SELECT 
    COUNT(*) as total_hikvision_assets,
    COUNT(DISTINCT sn) as unique_serial_numbers
FROM assets_datacenterasset
WHERE manufacturer_id IN (
    SELECT id FROM assets_manufacturer WHERE name = 'Hikvision'
);
-- Expected: 31 assets (10 existing + 21 new)

-- 3.2 Verify all 21 are now present
WITH missing_sns AS (
    SELECT unnest(ARRAY[
        'DS-2CD1043G0E-I20200427AAWRE30076984',
        'DS-2CD1121-I20200308AAWRE17568965',
        'DS-2CD1121-I20200308AAWRE17568450',
        'DS-2CD1121-I20200308AAWRE17568469',
        'DS-2CD1043G0E-I20200427AAWRE30076719',
        'DS-2CD1121-I20200308AAWRE17568933',
        'DS-2CD1143G0E-I20210227AAWRF58406256',
        'DS-2CD1121-I20200308AAWRE17568170',
        'DS-2CD1143G0E-I20210227AAWRF58406296',
        'DS-2CD1021-I20201119AAWRE99707505',
        'DS-2CD1121-I20200308AAWRE17568951',
        'DS-2CD1121-I20200308AAWRE17568954',
        'DS-2CD1121-I20200308AAWRE17568952',
        'DS-2CD1121-I20200308AAWRE17568968',
        'DS-2CD1121-I20200308AAWRE17568966',
        'DS-2CD1121-I20200308AAWRE17568967',
        'DS-2CD1121-I20200308AAWRE17568953',
        'DS-2CD1121-I20200308AAWRE17568949',
        'DS-2CD1121-I20200308AAWRE17568950',
        'DS-2CD1121-I20200308AAWRE17568948',
        'DS-2CD3121G0-I20200427AAWRE30076984'
    ]) AS sn
)
SELECT 
    COUNT(*) as recovered_count
FROM missing_sns m
INNER JOIN assets_datacenterasset a ON m.sn = a.sn;
-- Expected: 21 (all recovered)

-- 3.3 Check newly added assets details
SELECT 
    a.hostname,
    a.sn,
    m.name as model,
    a.status,
    se.name as service_environment,
    a.remarks,
    a.created
FROM assets_datacenterasset a
JOIN assets_assetmodel m ON a.model_id = m.id
LEFT JOIN assets_serviceenvironment se ON a.service_env_id = se.id
WHERE a.sn IN (
    'DS-2CD1043G0E-I20200427AAWRE30076984',
    'DS-2CD1121-I20200308AAWRE17568965',
    'DS-2CD1121-I20200308AAWRE17568450',
    'DS-2CD1121-I20200308AAWRE17568469',
    'DS-2CD1043G0E-I20200427AAWRE30076719',
    'DS-2CD1121-I20200308AAWRE17568933',
    'DS-2CD1143G0E-I20210227AAWRF58406256',
    'DS-2CD1121-I20200308AAWRE17568170',
    'DS-2CD1143G0E-I20210227AAWRF58406296',
    'DS-2CD1021-I20201119AAWRE99707505',
    'DS-2CD1121-I20200308AAWRE17568951',
    'DS-2CD1121-I20200308AAWRE17568954',
    'DS-2CD1121-I20200308AAWRE17568952',
    'DS-2CD1121-I20200308AAWRE17568968',
    'DS-2CD1121-I20200308AAWRE17568966',
    'DS-2CD1121-I20200308AAWRE17568967',
    'DS-2CD1121-I20200308AAWRE17568953',
    'DS-2CD1121-I20200308AAWRE17568949',
    'DS-2CD1121-I20200308AAWRE17568950',
    'DS-2CD1121-I20200308AAWRE17568948',
    'DS-2CD3121G0-I20200427AAWRE30076984'
)
ORDER BY a.hostname;

-- 3.4 Breakdown by model
SELECT 
    m.name as model,
    COUNT(*) as count
FROM assets_datacenterasset a
JOIN assets_assetmodel m ON a.model_id = m.id
WHERE a.manufacturer_id IN (
    SELECT id FROM assets_manufacturer WHERE name = 'Hikvision'
)
GROUP BY m.name
ORDER BY count DESC;
-- Expected:
-- DS-2CD1121-I: 14
-- DS-2CD1043G0E-I: 2
-- DS-2CD1143G0E-I: 2
-- DS-2CD1021-I: 1
-- DS-2CD3121G0-I: 1
-- (Plus any existing models)

-- ============================================================================
-- SECTION 4: MONITORING DATABASE VERIFICATION
-- ============================================================================

-- 4.1 Check CCTV metrics in dcim_events (PostgreSQL monitoring DB)
-- Connect to: 192.168.101.73:5432, database: dcim_sot
\c dcim_sot

-- Count CCTV events
SELECT 
    COUNT(*) as total_events,
    COUNT(DISTINCT serial_number) as unique_cameras,
    MIN(event_time) as oldest_event,
    MAX(event_time) as latest_event
FROM dcim_events
WHERE device_type = 'cctv';

-- List unique CCTVs in monitoring
SELECT 
    serial_number,
    hostname,
    COUNT(*) as event_count,
    MAX(event_time) as last_seen
FROM dcim_events
WHERE device_type = 'cctv'
GROUP BY serial_number, hostname
ORDER BY last_seen DESC;

-- Check for NO_SN entries (unidentified CCTVs)
SELECT 
    COUNT(*) as no_sn_count
FROM dcim_events
WHERE device_type = 'cctv' 
  AND serial_number = 'NO_SN';

-- ============================================================================
-- SECTION 5: AUDIT & LOGGING
-- ============================================================================

-- 5.1 Create audit log entry
INSERT INTO audit_log (
    timestamp,
    action,
    description,
    user_id,
    affected_records
) VALUES (
    NOW(),
    'BULK_IMPORT',
    'Re-registered 21 CCTV assets after migration recovery',
    (SELECT id FROM auth_user WHERE username = 'admin'),
    21
);

-- 5.2 Tag recovered assets
UPDATE assets_datacenterasset
SET remarks = CONCAT(
    COALESCE(remarks, ''),
    ' | Recovered: 2026-05-12 | Incident: Migration data loss'
)
WHERE sn IN (
    'DS-2CD1043G0E-I20200427AAWRE30076984',
    'DS-2CD1121-I20200308AAWRE17568965',
    'DS-2CD1121-I20200308AAWRE17568450',
    'DS-2CD1121-I20200308AAWRE17568469',
    'DS-2CD1043G0E-I20200427AAWRE30076719',
    'DS-2CD1121-I20200308AAWRE17568933',
    'DS-2CD1143G0E-I20210227AAWRF58406256',
    'DS-2CD1121-I20200308AAWRE17568170',
    'DS-2CD1143G0E-I20210227AAWRF58406296',
    'DS-2CD1021-I20201119AAWRE99707505',
    'DS-2CD1121-I20200308AAWRE17568951',
    'DS-2CD1121-I20200308AAWRE17568954',
    'DS-2CD1121-I20200308AAWRE17568952',
    'DS-2CD1121-I20200308AAWRE17568968',
    'DS-2CD1121-I20200308AAWRE17568966',
    'DS-2CD1121-I20200308AAWRE17568967',
    'DS-2CD1121-I20200308AAWRE17568953',
    'DS-2CD1121-I20200308AAWRE17568949',
    'DS-2CD1121-I20200308AAWRE17568950',
    'DS-2CD1121-I20200308AAWRE17568948',
    'DS-2CD3121G0-I20200427AAWRE30076984'
);

-- ============================================================================
-- SECTION 6: ROLLBACK (IF NEEDED)
-- ============================================================================

-- 6.1 Backup before import (RECOMMENDED)
CREATE TABLE assets_datacenterasset_backup_20260512 AS
SELECT * FROM assets_datacenterasset
WHERE manufacturer_id IN (
    SELECT id FROM assets_manufacturer WHERE name = 'Hikvision'
);

-- 6.2 Rollback if import fails
-- DELETE FROM assets_datacenterasset
-- WHERE sn IN (
--     'DS-2CD1043G0E-I20200427AAWRE30076984',
--     ... (list all 21 SNs)
-- )
-- AND created > '2026-05-12 00:00:00';

-- 6.3 Restore from backup
-- INSERT INTO assets_datacenterasset
-- SELECT * FROM assets_datacenterasset_backup_20260512;

-- ============================================================================
-- NOTES FOR DATABASE ADMIN
-- ============================================================================

/*
1. Run SECTION 1 queries BEFORE import untuk baseline
2. Perform import via API atau web UI
3. Run SECTION 3 queries AFTER import untuk verification
4. Run SECTION 4 queries untuk check monitoring integration
5. Run SECTION 5 queries untuk audit trail

Expected Results:
- Pre-import: ~10 Hikvision assets
- Post-import: 31 Hikvision assets (10 + 21)
- All 21 missing SNs should be found
- Monitoring should show metrics from all 31 CCTVs

Troubleshooting:
- If count != 31: Check foreign key constraints
- If SNs not found: Check import logs
- If monitoring shows <31: Wait for next polling cycle (120s)

Contact: Infrastructure Monitoring Team
Date: 2026-05-12
*/
