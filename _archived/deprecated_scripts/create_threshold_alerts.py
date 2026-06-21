#!/usr/bin/env python3
"""Create Elasticsearch Watchers for DCIM Threshold Monitoring.

Watchers log alerts to a dedicated index: dcim-alerts
Uses native ES Watcher (already running).

Thresholds:
1. Server Temperature > 75C (Critical)
2. UPS Battery < 50% (Warning)
3. UPS Load > 80% (Warning)
4. NAS Disk Temperature > 55C (Warning)
5. NVR Memory Usage > 90% (Warning)
6. Network Switch CPU > 85% (Warning)
"""
import requests
import json

ES = 'https://10.70.0.56:9200'
AUTH = ('elastic', 'C+H+pFb*aIAqWcOo-X8q')
HEADERS = {'Content-Type': 'application/json'}


def put_watcher(watcher_id, body):
    r = requests.put(f'{ES}/_watcher/watch/{watcher_id}',
                     auth=AUTH, headers=HEADERS, json=body, verify=False)
    if r.ok:
        print(f'  OK {watcher_id}')
    else:
        print(f'  FAIL {watcher_id}: {r.status_code} {r.text[:150]}')
    return r.ok


def make_watcher(device_type, agg_field, comparator, threshold, severity, description):
    cond_op = ">" if comparator == "gt" else "<"
    agg_type = "max" if comparator == "gt" else "min"

    return {
        "trigger": {"schedule": {"interval": "2m"}},
        "input": {
            "search": {
                "request": {
                    "indices": ["dcim-metrics-unified-*"],
                    "body": {
                        "size": 0,
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"device_type.keyword": device_type}},
                                    {"exists": {"field": agg_field}},
                                    {"range": {"@timestamp": {"gte": "now-5m"}}}
                                ]
                            }
                        },
                        "aggs": {
                            "check": {agg_type: {"field": agg_field}},
                            "hosts": {
                                "terms": {"field": "hostname.keyword", "size": 10},
                                "aggs": {"val": {agg_type: {"field": agg_field}}}
                            }
                        }
                    }
                }
            }
        },
        "condition": {
            "script": {
                "source": f"return ctx.payload.aggregations.check.value != null && ctx.payload.aggregations.check.value {cond_op} {threshold}",
                "lang": "painless"
            }
        },
        "actions": {
            "log_alert": {
                "logging": {
                    "text": f"DCIM ALERT [{severity.upper()}] {description}: value={{{{ctx.payload.aggregations.check.value}}}} threshold={threshold}"
                }
            },
            "index_alert": {
                "index": {
                    "index": "dcim-alerts"
                },
                "transform": {
                    "script": {
                        "source": """
                            def result = new HashMap();
                            result.put('alert_name', params.description);
                            result.put('severity', params.severity);
                            result.put('device_type', params.device_type);
                            result.put('metric_field', params.agg_field);
                            result.put('threshold', params.threshold);
                            result.put('current_value', ctx.payload.aggregations.check.value);
                            result.put('timestamp', ctx.execution_time);
                            def hosts = new ArrayList();
                            for (def bucket : ctx.payload.aggregations.hosts.buckets) {
                                hosts.add(bucket.key + '=' + bucket.val.value);
                            }
                            result.put('affected_hosts', hosts);
                            return ['_doc': result];
                        """,
                        "lang": "painless",
                        "params": {
                            "description": description,
                            "severity": severity,
                            "device_type": device_type,
                            "agg_field": agg_field,
                            "threshold": threshold
                        }
                    }
                }
            }
        },
        "metadata": {
            "description": description,
            "severity": severity
        }
    }


def main():
    print('=== Creating DCIM Threshold Watchers ===\n')

    watchers = [
        ("dcim-alert-server-temp", "server", "raw_fields.srv_reading_celsius", "gt", 75, "critical", "Server Temperature >75C"),
        ("dcim-alert-ups-battery", "ups", "raw_fields.battery_capacity", "lt", 50, "warning", "UPS Battery <50%"),
        ("dcim-alert-ups-load", "ups", "raw_fields.output_load", "gt", 80, "warning", "UPS Load >80%"),
        ("dcim-alert-nas-disk-temp", "nas", "raw_fields.diskTemp", "gt", 55, "warning", "NAS Disk Temp >55C"),
        ("dcim-alert-nvr-memory", "nvr", "raw_fields.memoryUsagePct", "gt", 90, "warning", "NVR Memory >90%"),
        ("dcim-alert-net-cpu", "network_switch", "raw_fields.cpu_load", "gt", 85, "warning", "Network CPU >85%"),
    ]

    ok_count = 0
    for wid, dtype, field, comp, thresh, sev, desc in watchers:
        body = make_watcher(dtype, field, comp, thresh, sev, desc)
        if put_watcher(wid, body):
            ok_count += 1

    print(f'\n=== {ok_count}/{len(watchers)} watchers created ===')
    print('Evaluate every 2 min. Alerts indexed to: dcim-alerts')


if __name__ == '__main__':
    main()
