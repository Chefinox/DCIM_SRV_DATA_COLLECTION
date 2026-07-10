#!/usr/bin/env python3
"""
SIEM Pipeline Diagnostic Script
Checks all components of the SIEM data flow:
1. NiFi container status
2. Kafka topic existence and data
3. Consumer service status
4. Elasticsearch index
"""

import subprocess
import json
import sys
from datetime import datetime
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(msg):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{msg}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

def print_ok(msg):
    print(f"{GREEN}✓ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}✗ {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}⚠ {msg}{RESET}")

def run_command(cmd):
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def check_nifi_container():
    """Check if NiFi container is running"""
    print_header("1. NiFi Container Status")
    
    rc, stdout, stderr = run_command("docker ps --filter name=dcim-nifi --format '{{.Names}}\t{{.Status}}'")
    
    if rc == 0 and stdout.strip():
        print_ok(f"NiFi container is running: {stdout.strip()}")
        return True
    else:
        print_error("NiFi container is NOT running")
        print(f"   Try: docker ps -a | grep nifi")
        return False

def check_nifi_port():
    """Check if NiFi is listening on port 5140"""
    print_header("2. NiFi Port 5140 (ListenSyslog)")
    
    rc, stdout, stderr = run_command("ss -tuln | grep ':5140'")
    
    if rc == 0 and stdout.strip():
        print_ok("Port 5140 is listening")
        for line in stdout.strip().split('\n'):
            print(f"   {line}")
        return True
    else:
        print_error("Port 5140 is NOT listening")
        print_warning("   NiFi ListenSyslog processor might be stopped")
        return False

def check_kafka_topic():
    """Check if dcim.siem.alerts topic exists"""
    print_header("3. Kafka Topic: dcim.siem.alerts")
    
    # Try different Kafka containers
    containers = ["kafka-broker", "kafka1", "kafka2", "kafka3"]
    
    for container in containers:
        rc, stdout, stderr = run_command(
            f"docker exec {container} /opt/kafka/bin/kafka-topics.sh "
            f"--bootstrap-server localhost:9092 --list 2>/dev/null | grep siem"
        )
        
        if rc == 0 and "dcim.siem.alerts" in stdout:
            print_ok(f"Topic 'dcim.siem.alerts' exists (checked via {container})")
            return True, container
    
    print_error("Topic 'dcim.siem.alerts' NOT FOUND")
    print_warning("   Topic needs to be created or deployment script needs to run")
    return False, None

def check_kafka_data(kafka_container):
    """Check if topic has data"""
    print_header("4. Kafka Topic Data")
    
    if not kafka_container:
        print_warning("Skipping - no Kafka container found")
        return False
    
    cmd = (
        f"timeout 5 docker exec {kafka_container} "
        f"/opt/kafka/bin/kafka-console-consumer.sh "
        f"--bootstrap-server localhost:9092 "
        f"--topic dcim.siem.alerts "
        f"--from-beginning --max-messages 3 2>/dev/null"
    )
    
    rc, stdout, stderr = run_command(cmd)
    
    if stdout.strip():
        print_ok(f"Topic has data ({len(stdout.strip().split(chr(10)))} messages retrieved)")
        print("   Sample message:")
        for line in stdout.strip().split('\n')[:3]:
            print(f"   {line[:100]}...")
        return True
    else:
        print_error("Topic is EMPTY - no messages found")
        print_warning("   Problem is in data ingestion (NiFi ListenSyslog → Kafka)")
        return False

def check_consumer_service():
    """Check dcim-siem-es-consumer service"""
    print_header("5. Consumer Service: dcim-siem-es-consumer")
    
    rc, stdout, stderr = run_command("systemctl is-active dcim-siem-es-consumer 2>/dev/null")
    
    if rc == 0 and stdout.strip() == "active":
        print_ok("Service is ACTIVE")
        
        # Get recent logs
        rc2, logs, _ = run_command("journalctl -u dcim-siem-es-consumer -n 10 --no-pager -o cat")
        if logs.strip():
            print("   Recent logs:")
            for line in logs.strip().split('\n')[-5:]:
                print(f"   {line}")
        return True
    else:
        print_error(f"Service is NOT active: {stdout.strip()}")
        print_warning("   Try: sudo systemctl status dcim-siem-es-consumer")
        return False

def check_elasticsearch_index():
    """Check Elasticsearch indices"""
    print_header("6. Elasticsearch Index: dcim-siem-alerts-*")
    
    ES_URL = "https://10.70.0.56:9200/_cat/indices/dcim-siem-alerts-*?v"
    ES_AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")
    
    try:
        resp = requests.get(ES_URL, auth=ES_AUTH, verify=False, timeout=10)
        
        if resp.status_code == 200:
            output = resp.text.strip()
            if output and len(output.split('\n')) > 1:
                print_ok("SIEM indices found:")
                for line in output.split('\n'):
                    print(f"   {line}")
                return True
            else:
                print_error("No dcim-siem-alerts-* indices found")
                return False
        else:
            print_error(f"ES request failed: {resp.status_code}")
            return False
    except Exception as e:
        print_error(f"Cannot connect to Elasticsearch: {str(e)}")
        return False

def check_latest_documents():
    """Check latest documents in today's index"""
    print_header("7. Latest Documents in ES")
    
    today = datetime.now().strftime("%Y.%m.%d")
    index_name = f"dcim-siem-alerts-{today}"
    
    ES_URL = f"https://10.70.0.56:9200/{index_name}/_search"
    ES_AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")
    
    query = {
        "size": 3,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {"match_all": {}}
    }
    
    try:
        resp = requests.post(ES_URL, auth=ES_AUTH, json=query, verify=False, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            total = data.get('hits', {}).get('total', {}).get('value', 0)
            
            if total > 0:
                print_ok(f"Index {index_name} has {total} documents")
                print("   Latest 3 documents:")
                for hit in data['hits']['hits'][:3]:
                    timestamp = hit['_source'].get('@timestamp', 'N/A')
                    message = hit['_source'].get('message', str(hit['_source']))[:80]
                    print(f"   [{timestamp}] {message}...")
                return True
            else:
                print_error(f"Index {index_name} exists but has 0 documents")
                return False
        elif resp.status_code == 404:
            print_error(f"Index {index_name} does NOT exist")
            print_warning("   No data received today")
            return False
        else:
            print_error(f"ES query failed: {resp.status_code}")
            return False
    except Exception as e:
        print_error(f"Cannot query Elasticsearch: {str(e)}")
        return False

def main():
    print(f"\n{BLUE}SIEM Pipeline Diagnostic Tool{RESET}")
    print(f"{BLUE}Timestamp: {datetime.now().isoformat()}{RESET}")
    
    results = {}
    
    # Run all checks
    results['nifi_container'] = check_nifi_container()
    results['nifi_port'] = check_nifi_port()
    results['kafka_topic'], kafka_container = check_kafka_topic()
    results['kafka_data'] = check_kafka_data(kafka_container) if results['kafka_topic'] else False
    results['consumer_service'] = check_consumer_service()
    results['es_index'] = check_elasticsearch_index()
    results['es_documents'] = check_latest_documents()
    
    # Summary
    print_header("DIAGNOSTIC SUMMARY")
    
    passed = sum(1 for v in results.values() if v == True)
    total = len(results)
    
    print(f"\nChecks passed: {passed}/{total}")
    print("\nStatus per component:")
    print(f"  {'NiFi Container':<25} {'✓' if results['nifi_container'] else '✗'}")
    print(f"  {'NiFi Port 5140':<25} {'✓' if results['nifi_port'] else '✗'}")
    print(f"  {'Kafka Topic':<25} {'✓' if results['kafka_topic'] else '✗'}")
    print(f"  {'Kafka Has Data':<25} {'✓' if results['kafka_data'] else '✗'}")
    print(f"  {'Consumer Service':<25} {'✓' if results['consumer_service'] else '✗'}")
    print(f"  {'ES Index Exists':<25} {'✓' if results['es_index'] else '✗'}")
    print(f"  {'ES Has Documents':<25} {'✓' if results['es_documents'] else '✗'}")
    
    # Root cause analysis
    print_header("ROOT CAUSE ANALYSIS")
    
    if not results['nifi_container']:
        print(f"{RED}→ NiFi container is not running - start with 'docker-compose up -d'{RESET}")
    elif not results['nifi_port']:
        print(f"{RED}→ NiFi ListenSyslog processor is not running - check NiFi UI{RESET}")
    elif not results['kafka_topic']:
        print(f"{RED}→ Kafka topic doesn't exist - run deployment script{RESET}")
    elif not results['kafka_data']:
        print(f"{RED}→ No data in Kafka topic - check syslog source is sending to port 5140{RESET}")
    elif not results['consumer_service']:
        print(f"{RED}→ Consumer service is not running - start it with systemctl{RESET}")
    elif not results['es_documents']:
        print(f"{RED}→ Consumer is running but not writing to ES - check service logs{RESET}")
    else:
        print(f"{GREEN}→ All components operational! Data should be flowing.{RESET}")
    
    print()
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
