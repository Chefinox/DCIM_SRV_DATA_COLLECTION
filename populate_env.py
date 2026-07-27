import hvac

client = hvac.Client(url='http://127.0.0.1:8200')
with open('/home/infra/dcim_metrics_project/vault/config/role_id', 'r') as f:
    role_id = f.read().strip()
with open('/home/infra/dcim_metrics_project/vault/config/secret_id', 'r') as f:
    secret_id = f.read().strip()

client.auth.approle.login(role_id=role_id, secret_id=secret_id)

def get_pass(name):
    try:
        return client.secrets.kv.v2.read_secret_version(mount_point='secret', path=f'dcim/{name}', raise_on_deleted_version=False)['data']['data']['password']
    except Exception as e:
        print(f"Error reading {name}: {e}")
        return ""

elastic_pass = get_pass('elastic_pass')
kibana_pass = get_pass('kibana_pass')
sot_db_pass = get_pass('sot_db_pass')

with open('/home/infra/dcim_metrics_project/.env', 'w') as f:
    f.write(f'ELASTIC_PASSWORD="{elastic_pass}"\n')
    f.write(f'KIBANA_PASSWORD="{kibana_pass}"\n')
    f.write(f'SOT_DB_PASS="{sot_db_pass}"\n')

print("Generated .env successfully")
