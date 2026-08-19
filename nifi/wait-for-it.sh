#!/usr/bin/env bash
# wait-for-it.sh version 1
host="$1"
shift
port="$1"
shift

while ! nc -z "$host" "$port"; do
  sleep 1
done

exec "$@"
