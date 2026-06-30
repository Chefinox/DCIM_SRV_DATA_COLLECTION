#!/bin/bash
# Cron job to maintain Redis CMDB cache
# Run every hour until PostgreSQL connection is restored

cd /home/infra/dcim_metrics_project
python3 scripts/populate_redis_minimal.py >> logs/redis_populate.log 2>&1

# Log completion
echo "$(date '+%Y-%m-%d %H:%M:%S') - Redis cache refreshed" >> logs/redis_populate.log
