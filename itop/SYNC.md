# NetBox to iTop Synchronization

## Purpose

`sync/sync_netbox_to_itop.py` reads NetBox REST API data and upserts iTop CMDB objects. Sync is repeatable and idempotent.

## Source

NetBox endpoint:

`http://10.70.0.20:9008/`

Imported endpoints:

- sites
- racks
- manufacturers
- device roles
- device types
- devices
- interfaces
- IP addresses
- virtual machines
- VM interfaces
- clusters
- platforms
- tenants
- VLANs
- cables optional, configured but skipped by default

## Identity and duplicate prevention

Each iTop class has one uniqueness key in `sync/mapping.yaml`.

Default keys:

- CI classes: `name`
- IPAddress: `ip`
- Brand: `name`

Before write, sync runs `core/get` using uniqueness key. If one object exists, sync updates it. If none exists, sync creates it. If more than one exists, sync fails object and logs duplicate error.

## Incremental sync

State file:

`/state/netbox_itop_state.json`

After full successful run, sync records `last_successful_started_at`. Next run requests NetBox objects with `last_updated__gte` where endpoint supports it. Reference endpoints such as sites/racks/manufacturers are refreshed every run to preserve relationship resolution.

If run has failures, state is not advanced.

## Relationships

Relationship fields populated during upsert:

- Rack → Site: `location_id`
- Device → Rack: `rack_id`
- Interface → Device or VM: `connectableci_id`
- IP → Interface: `ipinterface_id`
- VM → Hypervisor: `virtualhost_id`
- Device → Manufacturer: `brand_id`
- Cluster → Nodes: reserved mapping via relation class in `mapping.yaml`

Some iTop class/field names can vary by installed modules. If a write fails with unknown class or attribute, adjust `sync/mapping.yaml` or installed iTop modules, then rerun sync.

## Run once

Set environment variables first, then run:

`python sync_netbox_to_itop.py --mapping mapping.yaml`

Dry run:

`python sync_netbox_to_itop.py --mapping mapping.yaml --dry-run`

## Daemon mode

Container runs daemon mode by default:

`python /app/sync_netbox_to_itop.py --daemon --mapping /app/mapping.yaml`

Interval controlled by `SYNC_INTERVAL_SECONDS`.

## Observability

Health endpoint inside sync container:

- `/health`
- `/metrics`

Logs are JSON structured fields:

- `sync_started`
- `sync_completed`
- `sync_completed_with_failures`
- `object_sync_failed`
- `sync_failed`

Metrics:

- `netbox_itop_sync_objects_total{kind,status}`
- `netbox_itop_sync_errors_total{stage}`
- `netbox_itop_sync_last_success_timestamp`
- `netbox_itop_sync_last_run_status`

## Failed object retry

Failures remain in state only for visibility. Retry occurs naturally on next run because state advances only after no failures.

## Data consistency checks

Sync enforces:

- object uniqueness lookup before write
- duplicate iTop detection per class/key
- relationship assignment by NetBox IDs resolved to iTop IDs
- no state advancement on failed run
- structured failed import logging

## Mapping edits

Edit `sync/mapping.yaml` when:

- iTop installed class name differs
- iTop attribute name differs
- device role should map to different CI class
- custom extension adds proper Cluster/Application Service classes

After edit:

`docker compose restart netbox-itop-sync`
