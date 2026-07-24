import redis
r = redis.Redis(host='127.0.0.1', port=6379, db=1)
cursor = 0
count = 0
while True:
    cursor, keys = r.scan(cursor, match='itop_sync:*', count=1000)
    if keys:
        r.delete(*keys)
        count += len(keys)
    if cursor == 0:
        break
print(f"Flushed {count} itop_sync keys.")
