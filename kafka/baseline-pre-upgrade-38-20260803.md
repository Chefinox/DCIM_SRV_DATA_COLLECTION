# BASELINE KESEHATAN PIPELINE PRE-UPGRADE 3.8.x
Timestamp: 2026-08-03 09:57:27 
Broker Version: Apache Kafka 3.7.0

## 1. UNDER-REPLICATED PARTITIONS
```

```

## 2. UNAVAILABLE PARTITIONS
```

```

## 3. CONSUMER GROUPS STATUS
### Consumer Group: nifi-enrichment-group
```
Error: Consumer group 'nifi-enrichment-group' does not exist.
```

### Consumer Group: dcim_itop_group_v8
```
Error: Consumer group 'dcim_itop_group_v8' does not exist.
```

### Consumer Group: dcim-postgres-consumer-v2
```
Error: Consumer group 'dcim-postgres-consumer-v2' does not exist.
```

### Consumer Group: dcim-siem-es-consumer-2
```
GROUP                   TOPIC            PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim-siem-es-consumer-2 dcim.siem.alerts 4          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 5          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 6          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 2          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 1          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 11         -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 7          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 3          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 10         -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 0          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 9          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
dcim-siem-es-consumer-2 dcim.siem.alerts 8          -               0               -               rdkafka-55827ee9-5efa-4c6a-b386-fe3893b2bb5f /10.70.0.56     rdkafka
```

### Consumer Group: dcim-analytics-bridge
```
GROUP                 TOPIC                PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim-analytics-bridge dcim.enriched.events 7          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 8          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 3          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 10         -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 9          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 5          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 2          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 4          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 1          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 11         -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 6          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
dcim-analytics-bridge dcim.enriched.events 0          -               0               -               rdkafka-9961ef72-2ad4-46a2-bc3c-7fcfc36e9468 /10.70.0.56     rdkafka
```

### Consumer Group: dcim_python_normalizer_group
```
GROUP                        TOPIC                              PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 8          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              2          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              3          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 0          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 3          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              10         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              4          46              46              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 11         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 7          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 7          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 4          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              7          47              47              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           5          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              11         52              52              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 3          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               5          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               10         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           10         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               2          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        8          605             605             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 10         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              2          73              73              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        4          608             608             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              6          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        11         689             689             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              9          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              3          36              36              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        6          622             622             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              8          45              45              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           9          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           8          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           4          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 6          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               1          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               9          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 9          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               6          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 9          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           1          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 4          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        1          752             752             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               0          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        5          643             643             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        10         654             654             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 0          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 5          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 5          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              0          42              42              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              8          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        9          654             654             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              9          47              47              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              5          25              25              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 2          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           7          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               4          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        7          647             647             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 1          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              1          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           3          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        0          740             740             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              5          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              1          51              51              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              6          36              36              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.snmp              10         40              40              0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 10         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               7          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        3          611             611             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           6          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           2          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           11         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              0          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 1          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               8          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 8          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.network.interfaces        2          632             632             0               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              4          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 6          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              11         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server.inventory 2          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.hardware.server           0          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               11         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.storage.nas               3          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.device.isapi              7          -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
dcim_python_normalizer_group dcim.raw.power.ups                 11         -               0               -               rdkafka-f5baca40-80d7-47c9-9039-79cbc1fc8ced /10.70.0.56     rdkafka
```

### Consumer Group: dcim-es-consumer
```
GROUP            TOPIC                PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                  HOST            CLIENT-ID
dcim-es-consumer dcim.enriched.events 7          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 8          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 3          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 10         -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 9          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 5          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 2          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 4          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 1          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 11         -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 6          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
dcim-es-consumer dcim.enriched.events 0          -               0               -               rdkafka-4b441a18-7753-406c-a7ce-7c1cb5b7a08d /10.70.0.56     rdkafka
```

## 4. METADATA QUORUM STATUS
```
ClusterId:              Some(5L6g3nShT-eMCtK--X86sw)
LeaderId:               3
LeaderEpoch:            35400
HighWatermark:          2130635
MaxFollowerLag:         0
MaxFollowerLagTimeMs:   456
CurrentVoters:          [1,2,3]
CurrentObservers:       []
```