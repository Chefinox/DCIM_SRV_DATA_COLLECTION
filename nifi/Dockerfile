FROM apache/nifi:1.24.0

USER root

# Install Python OS dependencies
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python Libraries
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Revert to default NiFi user for security
USER nifi
