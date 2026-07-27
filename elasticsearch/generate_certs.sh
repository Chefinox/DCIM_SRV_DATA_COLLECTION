#!/bin/bash
set -e
echo "Generating certificates..."
mkdir -p certs
docker run --rm -v $(pwd)/certs:/certs -u 0 docker.elastic.co/elasticsearch/elasticsearch:9.3.1 bash -c "
  bin/elasticsearch-certutil ca --silent --pem -out /certs/ca.zip
  unzip -o /certs/ca.zip -d /certs
  echo -e 'instances:\n  - name: elasticsearch\n    dns:\n      - elasticsearch\n      - localhost\n    ip:\n      - 127.0.0.1\n      - 10.70.0.56' > /certs/instances.yml
  bin/elasticsearch-certutil cert --silent --pem -out /certs/certs.zip --in /certs/instances.yml --ca-cert /certs/ca/ca.crt --ca-key /certs/ca/ca.key
  unzip -o /certs/certs.zip -d /certs
  chown -R 1000:0 /certs
  chmod -R 755 /certs
"
echo "Certificates generated in ./certs"
