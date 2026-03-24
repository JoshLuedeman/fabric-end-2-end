# Real-Time Hub Setup Guide

> **Tales & Timber** — Fabric Real-Time Hub Configuration

The Real-Time Hub is the tenant-wide portal for discovering, managing, and consuming all data streams in your Microsoft Fabric environment. This guide walks through configuring the hub after the Terraform infrastructure has been deployed.

## Prerequisites

- Fabric capacity provisioned (`tt-fabric-{environment}`, F8 or higher)
- All 8 workspaces created (see `infra/environments/{dev,prod}/main.tf`)
- Eventhouse + KQL database deployed (`tt_eventhouse` / `tt_kqldb`)
- Eventstream created (`tt-change-events`)
- SQL Database operational (`tt_operational_db`)
- Event Hub namespace configured (`tt-eventhub-ns`)

## Stream Topology Overview

| # | Stream                  | Source                          | Destination        | Avg Events/s |
|---|-------------------------|---------------------------------|--------------------|--------------|
| 1 | POS Transactions        | SQL DB → Change Event Streaming | Eventhouse (KQL)   | 3.0          |
| 2 | Inventory Changes       | SQL DB → Change Event Streaming | Eventhouse (KQL)   | 1.0          |
| 3 | IoT Sensor Telemetry    | IoT Simulator → Event Hub       | Eventhouse (KQL)   | 100          |
| 4 | Customer Interactions   | SQL DB → Change Event Streaming | Eventhouse (KQL)   | 0.5          |
| 5 | Web Clickstream         | Lakehouse bronze (batch)        | Eventhouse (KQL)   | 50           |

> Full schema and throughput details: [`hub_topology.json`](./hub_topology.json)

---

## Step 1: Open Real-Time Hub

1. Navigate to the **Fabric portal** → [https://app.fabric.microsoft.com](https://app.fabric.microsoft.com)
2. In the left navigation, click **Real-Time Hub** (under the "Real-Time Intelligence" workload)
3. You should see the tenant-wide stream catalog — initially empty until streams are connected

---

## Step 2: Verify Change Event Streaming (Streams 1, 2, 4)

These three streams originate from the SQL Database via Change Event Streaming and flow through the existing Eventstream.

1. Open workspace **tt-data-warehouse-{environment}**
2. Navigate to **tt_operational_db** → **Settings** → **Change Event Streaming**
3. Confirm the following tables are enabled:
   - `dbo.Transactions` — POS transaction headers
   - `dbo.TransactionItems` — POS line items
   - `dbo.Inventory` — Stock-level changes
   - `dbo.CustomerInteractions` — CRM interactions
4. Verify the target Eventstream is set to **tt-change-events**
5. Confirm capture mode is **Incremental**

Once enabled, these streams will automatically appear in the Real-Time Hub catalog.

---

## Step 3: Verify IoT Telemetry Stream (Stream 3)

1. Open workspace **tt-real-time-{environment}**
2. Navigate to the **tt-change-events** Eventstream (or create a dedicated `tt-iot-events` Eventstream)
3. Confirm the **Azure Event Hub** source is configured:
   - Namespace: `tt-eventhub-ns`
   - Event Hub: `tt-events`
   - Consumer Group: `$Default`
   - Data Format: JSON
4. Verify the IoT simulator is running:
   ```bash
   cd streaming
   npm run dev          # DRY_RUN=true by default — logs to console
   ```
5. To push events to Event Hub:
   ```bash
   DRY_RUN=false EVENT_HUB_CONNECTION_STRING="<connection-string>" npm start
   ```
6. The IoT stream should appear in Real-Time Hub once events are flowing

---

## Step 4: Configure Web Clickstream Micro-Batch (Stream 5)

The clickstream uses a batch-to-streaming bridge pattern:

1. Open workspace **tt-data-engineering-{environment}**
2. Verify clickstream data lands in **lh_bronze** → `Tables/bronze_clickstream`
3. Create a **Data Pipeline** or **Notebook** that:
   - Reads new rows from `bronze_clickstream` every 5 minutes
   - Writes them to Eventhouse `tt_kqldb.WebClickstream`
4. Alternatively, create a **KQL Database Shortcut** from Eventhouse to the Lakehouse Delta table for near-real-time access without a pipeline

---

## Step 5: Register Streams in Real-Time Hub

After all sources are flowing, register them for discoverability:

1. Open **Real-Time Hub** in the Fabric portal
2. Click **+ Get events** in the top toolbar
3. For each stream, select the appropriate source type:

   | Stream                | Source Type in Hub                     |
   |-----------------------|----------------------------------------|
   | POS Transactions      | Fabric Eventstream                     |
   | Inventory Changes     | Fabric Eventstream                     |
   | IoT Sensor Telemetry  | Azure Event Hub                        |
   | Customer Interactions | Fabric Eventstream                     |
   | Web Clickstream       | Fabric Lakehouse (Delta shortcut)      |

4. For each stream, add descriptive metadata:
   - **Name**: Use the stream names from `hub_topology.json`
   - **Description**: Copy the description field
   - **Tags**: Add tags like `real-time`, `cdc`, `iot`, `batch`, `tt`

---

## Step 6: Connect Consumers

For each stream, connect the downstream consumers:

### POS Transactions → Real-Time Dashboard
1. Open the **Store Operations Live** dashboard definition (`src/kql/dashboards/store_operations_live.json`)
2. In the Fabric portal, navigate to **tt-real-time-{environment}** workspace
3. Create a **Real-Time Dashboard** and import tile queries from the JSON definition
4. Set the data source to `tt_kqldb`
5. Enable auto-refresh (30-second interval)

### POS Transactions → Anomaly Detection
1. Anomaly detection queries in `src/kql/queries/sales_anomaly_detection.kql` run against the same KQL database
2. These can be pinned as dashboard tiles or triggered via Data Activator

### IoT Telemetry → Environment Monitoring
1. Import tile queries from `src/kql/dashboards/iot_monitoring_live.json`
2. Create a dashboard in the **tt-real-time-{environment}** workspace
3. Set auto-refresh to 15 seconds for temperature/humidity tiles

### Inventory Changes → Stock Alerts
1. Inventory alert queries in `src/kql/queries/inventory_alerts.kql` detect low-stock conditions
2. Connect to Data Activator (Reflex) for automated alert emails

---

## Step 7: Validate End-to-End Data Flow

1. **Start the OLTP simulator** (generates Streams 1, 2, 4):
   ```bash
   cd simulator
   python oltp_simulator.py --rate-multiplier 2.0
   ```

2. **Start the IoT simulator** (generates Stream 3):
   ```bash
   cd streaming
   DRY_RUN=false EVENT_HUB_CONNECTION_STRING="<conn-str>" npm start
   ```

3. **Verify data arrival** in KQL database:
   ```kql
   // Check recent POS transactions
   RealtimeSales
   | where Timestamp > ago(5m)
   | count

   // Check recent IoT readings
   RealtimeIoT
   | where ReadingTimestamp > ago(5m)
   | count

   // Check inventory snapshots
   InventorySnapshot
   | summarize arg_max(SnapshotTimestamp, *) by ProductId, StoreId
   | count
   ```

4. **Open Real-Time Hub** and verify all 5 streams show as **Active** with event counts increasing

---

## Monitoring & Troubleshooting

### Stream Health Checks

| Check                          | How                                                         |
|--------------------------------|-------------------------------------------------------------|
| Eventstream throughput         | Eventstream → Monitor tab → Events In/Out per minute        |
| KQL ingestion lag              | `.show ingestion failures` in KQL database                  |
| Event Hub consumer lag         | Azure Portal → Event Hub → Consumer group → Lag metrics     |
| Simulator errors               | Check simulator console output for `[ERROR]` lines          |
| Change Event Streaming status  | SQL Database → Settings → Change Event Streaming → Status   |

### Common Issues

| Symptom                        | Likely Cause                      | Resolution                          |
|--------------------------------|-----------------------------------|-------------------------------------|
| No events in KQL database      | Eventstream not activated         | Open Eventstream → click **Activate** |
| IoT events missing             | Event Hub connection string wrong | Verify `EVENT_HUB_CONNECTION_STRING` |
| High ingestion latency         | Capacity throttled                | Scale up from F8 to F16             |
| Schema mismatch errors         | Table mapping out of sync         | Re-run `src/kql/ingestion/realtime_sales.kql` to recreate tables |
| Clickstream not updating       | Pipeline schedule paused          | Resume the micro-batch pipeline     |

---

## Capacity Planning

| Metric                         | Demo (10 stores)   | Full Scale (500 stores) |
|--------------------------------|--------------------|-------------------------|
| POS events/sec                 | 3                  | 150                     |
| IoT events/sec                 | 10                 | 100                     |
| Inventory events/sec           | 1                  | 50                      |
| Customer interactions/sec      | 0.5                | 25                      |
| Clickstream events/sec         | 5                  | 50                      |
| **Total events/sec**           | **~20**            | **~375**                |
| Recommended Fabric SKU         | F8                 | F32+                    |
| Eventhouse storage (90 days)   | ~5 GB              | ~250 GB                 |
