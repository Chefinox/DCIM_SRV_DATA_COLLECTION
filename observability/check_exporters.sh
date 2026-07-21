#!/bin/bash
# =============================================================================
# Network verification: srv-rnd-dcim (10.70.0.56) → external Prometheus (10.70.0.25)
# Run this script on srv-rnd-dcim to verify all exporter ports are accessible.
# =============================================================================

PROMETHEUS_HOST="10.70.0.25"
DCIM_HOST="10.70.0.56"

echo "============================================"
echo "  Prometheus/Grafana Exporter Health Check"
echo "  Host: ${DCIM_HOST} → External: ${PROMETHEUS_HOST}"
echo "  Date: $(date)"
echo "============================================"
echo ""

PASS=0
FAIL=0

check_endpoint() {
    local name=$1
    local port=$2
    local path=${3:-/metrics}
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "http://${DCIM_HOST}:${port}${path}" 2>/dev/null)
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "  ✅ ${name} (port ${port}) — HTTP ${HTTP_CODE}"
        PASS=$((PASS+1))
    else
        echo "  🔴 ${name} (port ${port}) — HTTP ${HTTP_CODE} — FAILED"
        FAIL=$((FAIL+1))
    fi
}

echo "--- Exporter Endpoints ---"
check_endpoint "Node Exporter"        9100
check_endpoint "PostgreSQL Exporter"  9187
check_endpoint "Redis Exporter"       9121
check_endpoint "Kafka Exporter"       9308
check_endpoint "Elasticsearch Exp."   9114
check_endpoint "Prometheus"           9090 "/-/healthy"
check_endpoint "Grafana"              3000 "/api/health"

echo ""
echo "--- External Ping Test (${PROMETHEUS_HOST}) ---"
if ping -c 1 -W 2 ${PROMETHEUS_HOST} >/dev/null 2>&1; then
    echo "  ✅ ${PROMETHEUS_HOST} reachable via ICMP"
else
    echo "  🔴 ${PROMETHEUS_HOST} NOT reachable via ICMP"
fi

echo ""
echo "============================================"
echo "  Result: ${PASS} PASS, ${FAIL} FAIL"
echo "============================================"
