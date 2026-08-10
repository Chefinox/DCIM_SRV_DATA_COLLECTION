# BASELINE KESEHATAN PIPELINE PRE-UPGRADE 4.1.x SIMULTANEOUS
Timestamp: 2026-08-03 15:41:32 
Broker Version: Apache Kafka 3.7.0

## 1. UNDER-REPLICATED PARTITIONS
```

```

## 2. UNAVAILABLE PARTITIONS
```

```

## 3. METADATA QUORUM STATUS
```
ClusterId:              Some(5L6g3nShT-eMCtK--X86sw)
LeaderId:               2
LeaderEpoch:            35986
HighWatermark:          2170904
MaxFollowerLag:         0
MaxFollowerLagTimeMs:   277
CurrentVoters:          [1,2,3]
CurrentObservers:       []
```

## 4. CONSUMER GROUPS STATUS
### Consumer Group: nifi-enrichment-group
```
GROUP                 TOPIC                  PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                                           HOST            CLIENT-ID
nifi-enrichment-group dcim.normalized.events 7          38137           38137           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 8          37351           37351           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 10         32367           32367           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 2          41632           41632           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 9          32375           32375           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 3          35218           35218           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 11         34803           34803           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 6          36381           36381           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 5          33379           33379           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 1          38352           38352           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 0          30704           30704           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
nifi-enrichment-group dcim.normalized.events 4          32365           32365           0               consumer-nifi-enrichment-group-1-b9f4abfe-49c0-43cb-ade7-d49877704d34 /10.70.0.56     consumer-nifi-enrichment-group-1
```

### Consumer Group: dcim_itop_group_v8
```
GROUP              TOPIC                  PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim_itop_group_v8 dcim.normalized.events 7          10420           38137           27717           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 8          12327           37351           25024           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 10         8816            32367           23551           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 2          10470           41632           31162           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 9          10346           32375           22029           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 3          10675           35218           24543           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 11         11592           34803           23211           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 6          9633            36381           26748           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 5          8661            33379           24718           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 1          12348           38352           26004           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 0          9314            30704           21390           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
dcim_itop_group_v8 dcim.normalized.events 4          8434            32365           23931           rdkafka-c0bb80ed-f666-44dc-a548-806d8bc9a1a0 /10.70.0.56     rdkafka
```

### Consumer Group: dcim-postgres-consumer-v2
```
GROUP                     TOPIC                PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim-postgres-consumer-v2 dcim.enriched.events 7          29238           29238           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 8          31541           31541           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 3          29214           29214           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 10         30392           30392           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 9          29981           29981           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 5          29581           29581           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 2          29619           29619           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 4          29554           29559           5               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 1          30696           30696           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 11         29919           29919           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 6          30390           30390           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
dcim-postgres-consumer-v2 dcim.enriched.events 0          29225           29225           0               rdkafka-91d2bd1b-8f5f-49fd-9112-ed53906a58de /10.70.0.56     rdkafka
```

### Consumer Group: dcim-siem-es-consumer-2
```
GROUP                   TOPIC            PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim-siem-es-consumer-2 dcim.siem.alerts 4          -               8               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 5          -               17              -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 6          -               23              -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 2          -               20              -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 1          -               10              -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 11         -               9               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 7          -               12              -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 3          -               11              -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 10         -               3               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 0          -               3               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 9          -               13              -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 8          -               3               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
```

### Consumer Group: dcim-analytics-bridge
```
GROUP                 TOPIC                PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim-analytics-bridge dcim.enriched.events 7          29238           29314           76              rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 8          31541           31550           9               rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 3          29214           29338           124             rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 10         30392           30470           78              rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 9          29981           30102           121             rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 5          29581           29692           111             rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 2          29619           29694           75              rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 4          29559           29629           70              rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 1          30696           30792           96              rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 11         29919           29958           39              rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 6          30390           30490           100             rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 0          29225           29355           130             rdkafka-063d5f1a-9a8f-4bc2-9f42-b2f2657f9a07 /10.70.0.56     rdkafka
```

### Consumer Group: dcim_python_normalizer_group
```
GROUP                        TOPIC                              PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 8          -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              2          20              20              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              3          16              16              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 0          23              23              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 3          22              22              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              10         20              20              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              4          645             645             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 11         -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 7          34              34              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 7          -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 4          22              22              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              7          637             637             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           5          22              22              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              11         654             654             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 3          -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               5          24              24              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               10         22              22              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           10         28              28              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               2          30              30              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        8          9324            9324            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 10         28              28              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              2          634             634             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        4          9150            9150            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              6          28              28              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        11         9325            9325            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              9          20              20              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              3          621             621             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        6          9024            9024            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              8          672             672             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           9          28              28              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           8          36              36              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           4          40              40              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 6          -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               1          30              30              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               9          32              32              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 9          24              24              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               6          32              32              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 9          -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           1          32              32              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 4          -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        1          9364            9364            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               0          24              24              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        5          9407            9407            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        10         9299            9299            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 0          -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 5          1               1               0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 5          25              25              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              0          597             597             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              8          26              26              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        9          9080            9080            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              9          572             572             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              5          611             611             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 2          20              20              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           7          28              28              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               4          32              32              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        7          9330            9330            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 1          -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              1          22              22              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           3          28              28              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        0          9440            9440            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              5          26              26              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              1          615             615             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              6          625             625             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              10         607             607             0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 10         -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               7          30              30              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        3          9171            9171            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           6          44              44              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           2          30              30              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           11         14              14              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              0          14              14              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 1          21              21              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               8          20              20              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 8          21              21              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        2          9218            9218            0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              4          32              32              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 6          16              16              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              11         26              26              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 2          -               0               -               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           0          32              32              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               11         34              34              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               3          34              34              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              7          22              22              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 11         22              22              0               rdkafka-706eba1d-6cad-4546-8fd8-38e011de9bdf /10.70.0.56     rdkafka
```

### Consumer Group: dcim-es-consumer
```
GROUP            TOPIC                PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim-es-consumer dcim.enriched.events 7          29314           29314           0               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 8          31550           31550           0               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 3          29338           29338           0               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 10         30460           30470           10              rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 9          30102           30102           0               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 5          29683           29692           9               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 2          29694           29694           0               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 4          29629           29629           0               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 1          30783           30792           9               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 11         29958           29958           0               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 6          30489           30490           1               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 0          29355           29355           0               rdkafka-8c1a9401-e620-4752-b4dd-757ac67e6ede /10.70.0.56     rdkafka
```
