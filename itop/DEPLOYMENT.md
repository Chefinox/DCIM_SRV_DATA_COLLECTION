# iTop Deployment Guide

Scope: deploy iTop Community Edition and populate data from NetBox only. Existing infrastructure stays unchanged.

## Files

- `docker-compose.yml` — iTop, MariaDB, NetBox sync service
- `.env.example` — required environment variables
- `mariadb/conf.d/itop.cnf` — MariaDB CMDB workload tuning
- `sync/sync_netbox_to_itop.py` — idempotent sync service
- `sync/mapping.yaml` — NetBox-to-iTop mapping

## Prerequisites

- Docker Engine
- Docker Compose v2
- Network access to NetBox: `http://10.70.0.20:9008/`
- NetBox API token with read access
- iTop initial setup completed after first boot

## Deploy

1. Copy environment template:

   `cp .env.example .env`

2. Edit `.env`:

   - set strong database passwords
   - set `ITOP_ADMIN_PASSWORD`
   - set `NETBOX_TOKEN`
   - set `ITOP_URL`
   - keep `ITOP_HTTP_BIND=127.0.0.1` unless reverse proxy already exists

3. Start stack:

   `docker compose up -d`

4. Open iTop:

   `http://localhost:8080`

5. Complete iTop web installer:

   - database host: `itop-db`
   - database name: value of `ITOP_DB_NAME`
   - database user: value of `ITOP_DB_USER`
   - database password: value of `ITOP_DB_PASSWORD`
   - install CMDB core modules
   - enable REST webservices
   - enable Synchro Data Sources module when installer offers modules

6. Create or confirm sync account:

   - recommended account: `ITOP_SYNC_USER`
   - grant rights to create/update CMDB CIs and relationships
   - use separate password in `ITOP_SYNC_PASSWORD`

7. Restart sync service after iTop setup:

   `docker compose restart netbox-itop-sync`

## Production settings

- Database exposed only inside Docker network.
- iTop HTTP binds to loopback by default.
- Secrets loaded from `.env`; never commit `.env`.
- Persistent volumes used for database, iTop files, and sync state.
- Healthchecks enabled for all services.
- Restart policy: `unless-stopped`.

## iTop configuration checklist

- CMDB module enabled.
- REST API enabled: `/webservices/rest.php` reachable from sync container.
- User auth works for `ITOP_SYNC_USER`.
- Synchro Data Sources module enabled for future iTop-native reconciliation.
- Classes available or mapped in `sync/mapping.yaml`:
  - Datacenter
  - Location/Site
  - Rack
  - PhysicalDevice
  - Server
  - Hypervisor
  - VirtualMachine
  - NetworkDevice/Switch
  - Firewall
  - PowerSource/UPS/PDU
  - LogicalVolume/Cluster placeholder
  - ApplicationSolution/Application Service

## Backup

### Database backup

Run from `itop/`:

`docker compose exec itop-db mariadb-dump -u root -p$ITOP_DB_ROOT_PASSWORD --single-transaction --routines --triggers itop > backups/itop-$(date +%F-%H%M%S).sql`

### Files backup

Back up Docker volumes:

- `itop_db_data`
- `itop_web_data`
- `sync_state`

Also back up:

- `.env` in secure secret storage
- `sync/mapping.yaml`
- `mariadb/conf.d/itop.cnf`

## Restore

1. Stop stack: `docker compose down`
2. Restore volumes or recreate stack.
3. Start database: `docker compose up -d itop-db`
4. Import dump into `ITOP_DB_NAME`.
5. Start full stack: `docker compose up -d`
6. Check iTop UI and sync logs.

## Upgrade

1. Read iTop release notes.
2. Back up database and files.
3. Update `itop-web` image tag in `docker-compose.yml`.
4. Run `docker compose pull`.
5. Start iTop only: `docker compose up -d itop-db itop-web`.
6. Run iTop upgrade wizard if prompted.
7. Start sync: `docker compose up -d netbox-itop-sync`.
8. Verify health and logs.

## MariaDB maintenance

Recommended periodic tasks:

- daily logical database backup
- weekly restore test
- monthly `ANALYZE TABLE` for large CMDB tables
- review slow query log `itop-slow.log`
- monitor InnoDB buffer pool hit ratio

Index recommendations:

- keep iTop default indexes intact
- ensure CI `name` fields stay indexed by iTop schema
- avoid manual schema changes unless validated against iTop upgrade path
- add custom indexes only after slow-query evidence
