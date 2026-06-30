# iTop Operational Runbook

## Start

`docker compose up -d`

## Stop

`docker compose down`

## Status

`docker compose ps`

## Logs

All services:

`docker compose logs -f`

Sync only:

`docker compose logs -f netbox-itop-sync`

## Force sync now

`docker compose exec netbox-itop-sync python /app/sync_netbox_to_itop.py --mapping /app/mapping.yaml`

## Reset sync state

Use only when full reconciliation needed.

1. Stop sync: `docker compose stop netbox-itop-sync`
2. Back up state volume.
3. Delete `/state/netbox_itop_state.json` inside sync container/volume.
4. Start sync: `docker compose start netbox-itop-sync`

## Health checks

iTop web:

`docker compose exec itop-web curl -fsS http://127.0.0.1/pages/UI.php`

Database:

`docker compose exec itop-db mariadb-admin ping -h 127.0.0.1 -u root -p$ITOP_DB_ROOT_PASSWORD`

Sync:

`docker compose exec netbox-itop-sync python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8088/health").read().decode())'`

## Backup schedule

Recommended:

- daily MariaDB dump
- daily sync state backup
- weekly full volume backup
- monthly restore test

## Troubleshooting

### iTop installer cannot connect to database

Check:

- `itop-db` healthy
- database credentials match `.env`
- database host set to `itop-db`

### Sync API authentication fails

Check:

- `ITOP_SYNC_USER`
- `ITOP_SYNC_PASSWORD`
- REST API enabled in iTop
- user profile can create/update CMDB objects

### NetBox API authentication fails

Check:

- `NETBOX_URL=http://10.70.0.20:9008/`
- `NETBOX_TOKEN`
- token read permissions
- network route from sync container

### Unknown iTop class or field

Cause: installed iTop module class names differ from mapping.

Fix:

1. Check iTop data model.
2. Edit `sync/mapping.yaml` class or field name.
3. Restart sync.

### Duplicate CI detected

Cause: existing iTop objects share same uniqueness key.

Fix:

1. Review sync log `Duplicate iTop objects`.
2. Merge/delete duplicate CI in iTop.
3. Rerun sync.

### Relationships missing

Check import order and mapping:

- sites before racks
- racks before devices
- devices/VMs before interfaces
- interfaces before IPs

If parent object failed, child relationship waits until next successful run.

### Sync state not advancing

Cause: one or more failed objects.

Fix:

1. Inspect `docker compose logs netbox-itop-sync`.
2. Fix class/field/duplicate/data issue.
3. Rerun sync.

## Security operations

- Store `.env` outside Git.
- Rotate NetBox token periodically.
- Use dedicated iTop sync account.
- Keep database network internal.
- Bind iTop to loopback unless protected by existing reverse proxy/firewall.
