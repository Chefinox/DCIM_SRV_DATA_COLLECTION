#!/usr/bin/env python3
"""
ST-318 Verification Script — Vault Integration & Audit Database Permissions
Author: Syauqi (DBA & Pipeline)
Date: 2026-07-30
"""

import os
import sys
import json
import psycopg2
import psycopg2.extras
import hvac

def check_vault_integration():
    print("=== 1. Checking Vault Integration & JWT Path ===")
    vault_addr = os.environ.get('VAULT_ADDR', 'http://10.70.0.56:8200')
    role_id_path = os.environ.get('VAULT_ROLE_ID_PATH', '/home/infra/dcim_metrics_project/vault/config/role_id')
    secret_id_path = os.environ.get('VAULT_SECRET_ID_PATH', '/home/infra/dcim_metrics_project/vault/config/secret_id')
    
    try:
        with open(role_id_path, 'r') as f:
            role_id = f.read().strip()
        with open(secret_id_path, 'r') as f:
            secret_id = f.read().strip()
            
        client = hvac.Client(url=vault_addr)
        client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        
        if not client.is_authenticated():
            print("❌ Vault AppRole authentication failed.")
            return False
            
        read_response = client.secrets.kv.v2.read_secret_version(
            mount_point='secret',
            path='dcim/jwt_verifier'
        )
        
        data = read_response.get('data', {}).get('data', {})
        print("✓ Vault AppRole authentication successful.")
        print("✓ Path 'secret/dcim/jwt_verifier' exists.")
        print(f"✓ Config keys present: {list(data.keys())}")
        print(f"✓ Vault path status: {data.get('status', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ Error checking Vault: {e}")
        return False


def check_audit_database():
    print("\n=== 2. Checking TimescaleDB/PostgreSQL Audit Log Permission ===")
    
    # Priority 1: TimescaleDB (port 5433, db dcim_analytics)
    # Priority 2: PostgreSQL (port 5432, db dcim_sot)
    db_configs = [
        {"host": os.environ.get('PGHOST', '127.0.0.1'), "port": os.environ.get('PGPORT', '5433'), "user": "analytics_user", "pass": "changeme", "dbname": "dcim_analytics"},
        {"host": os.environ.get('PGHOST', '127.0.0.1'), "port": "5432", "user": "sot_admin", "pass": "Inovasi@0918", "dbname": "dcim_sot"}
    ]
    
    conn = None
    connected_config = None
    
    for cfg in db_configs:
        try:
            conn = psycopg2.connect(
                host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["pass"], dbname=cfg["dbname"]
            )
            connected_config = cfg
            print(f"✓ Connected to DB '{cfg['dbname']}' on {cfg['host']}:{cfg['port']} as user '{cfg['user']}'.")
            break
        except Exception as e:
            print(f"⚠️ Connection attempt to {cfg['dbname']} on port {cfg['port']} failed: {e}")
            
    if not conn:
        print("❌ Could not connect to any target database.")
        return False


    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # Check table presence
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'audit_log';
        """)
        columns = cursor.fetchall()
        if not columns:
            print("❌ Table 'public.audit_log' does not exist.")
            return False
            
        col_names = [c['column_name'] for c in columns]
        print(f"✓ Table 'public.audit_log' found with {len(columns)} columns.")
        print(f"✓ Schema columns: {', '.join(col_names)}")

        # Test INSERT permission
        test_user = "syauqi_dba_st318_verifier"
        test_action = "ST318_PERMISSION_VERIFY"
        test_resource = "SYSTEM"
        
        cursor.execute("""
            INSERT INTO public.audit_log (user_id, action, resource_type, resource_id, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING log_id, timestamp;
        """, (test_user, test_action, test_resource, "ST-318", json.dumps({"status": "SUCCESS", "verification": "PASS"}), "127.0.0.1"))
        
        inserted_row = cursor.fetchone()
        conn.commit()
        print(f"✓ INSERT permission verified! Log ID: {inserted_row['log_id']} at {inserted_row['timestamp']}")

        # Test SELECT permission & query verification
        cursor.execute("""
            SELECT timestamp, user_id, action, resource_type, resource_id, details, ip_address
            FROM public.audit_log
            ORDER BY timestamp DESC
            LIMIT 5;
        """)
        recent_logs = cursor.fetchall()
        print(f"✓ SELECT permission verified! Retrieved {len(recent_logs)} recent audit logs.")
        
        print("\n--- Recent Audit Rows Evidence (Sanitized) ---")
        for log in recent_logs:
            print(f"  [{log['timestamp']}] User: {log['user_id']} | Action: {log['action']} | Resource: {log['resource_type']}:{log['resource_id']} | IP: {log['ip_address']}")
            
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Error verifying audit database: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("========================================================")
    print("   ST-318 SYAUQI ACTION ITEMS VERIFICATION RUNNER")
    print("========================================================")
    
    v_ok = check_vault_integration()
    db_ok = check_audit_database()
    
    print("\n========================================================")
    if v_ok and db_ok:
        print("🎉 ALL ST-318 SYAUQI ACTION ITEMS VERIFIED SUCCESSFULLY!")
        print("========================================================")
        sys.exit(0)
    else:
        print("❌ VERIFICATION FAILED. CHECK ERRORS ABOVE.")
        print("========================================================")
        sys.exit(1)
