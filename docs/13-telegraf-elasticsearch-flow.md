# Telegraf to Elasticsearch — Data Flow Architecture

## 📋 Overview

This document explains the technical pipeline that moves data from your physical infrastructure (UPS, Servers, Switches) into the Elasticsearch database.

---

## 🏗️ The Data Pipeline

The flow follows a standard **Poll ➡️ Buffer ➡️ Push** architecture:

1.  **Poll (Input):** Every 60 seconds, Telegraf connects to each device via SNMP or Redfish.
2.  **Buffer (Memory):** Metrics are stored in a local RAM buffer on the `srv-rnd-dcim` host.
3.  **Push (Output):** Telegraf batches these metrics and sends them to the Elasticsearch Bulk API.

---

## 🚀 Transmission Logic (Bulk API)

Telegraf uses the **Elasticsearch Output Plugin** for efficient data delivery.

### 1. Batching & Efficiency
Instead of sending a message for every single temperature reading, Telegraf groups hundreds of readings into a single HTTP POST request.
*   **API Endpoint:** `https://10.70.0.56:9200/_bulk`
*   **Method:** `POST`
*   **Authentication:** Basic Auth (`elastic` user)

### 2. Time-Series Storage (Daily Indices)
Documents are organized into daily indices based on the server's clock. This allows for easy maintenance and fast queries.
*   **Index Pattern:** `telegraf-metrics-YYYY.MM.DD`
*   **Creation:** Automatic (triggered by the first document of the day).

---

## 📄 Document Structure (JSON Schema)

Every metric in Elasticsearch is a JSON document. Below is how Telegraf maps our project's data:

| Component | JSON Key | Example |
| :--- | :--- | :--- |
| **Timestamp** | `@timestamp` | `"2026-04-15T12:00:00+07:00"` |
| **Measurement** | `measurement_name` | `"ups_apc"` / `"net_interface"` |
| **Tags (Metadata)** | `tag` | `"tag": {"agent_host": "172.16.35.1"}` |
| **Fields (Values)** | `{measurement_name}` | `"ups_apc": {"output_load": 15}` |

> 💡 **Discovery Tip:** Because fields are nested under the measurement name, you must always use the prefix in Kibana (e.g., `net_interface.if_in_octets`).

---

## 🛡️ Reliability Features

*   **In-Memory Buffering:** if the Elasticsearch server is busy or the network is down, Telegraf will hold your metrics in RAM.
*   **Persistent Failover:** If a specific document causes an error, Telegraf will log the error but continue sending other valid metrics.
*   **Compression:** Data is sent in a standard JSON stream, optimized for Elasticsearch's mapping engine.

---

## 🛠️ Monitoring the Flow

To check if the pipeline is healthy, run the following command on the monitoring server:

```bash
# Check for connection errors or authentication failures
journalctl -u telegraf --since "1 hour ago" | grep -i "elasticsearch"
```
