# Digital Twin Builder Setup Guide

> **Contoso Global Retail & Supply Chain** — Fabric Digital Twin Builder (Preview)

Digital Twin Builder in Microsoft Fabric lets you create live digital replicas of physical assets and business processes, backed by real-time telemetry from Eventhouse. This guide explains how to configure twins for the Contoso environment.

## Prerequisites

- Fabric capacity provisioned (F8+) with Digital Twin Builder enabled (Preview feature)
- Eventhouse deployed (`contoso_eventhouse` / `contoso_kqldb`)
- Real-time data flowing via Eventstream (see `src/realtime-hub/hub_setup_guide.md`)
- Twin model definitions in this directory:
  - [`store_twin_model.json`](./store_twin_model.json) — Retail store physical layout + equipment
  - [`supply_chain_twin_model.json`](./supply_chain_twin_model.json) — Supply chain network

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  Digital Twin Builder                        │
│                                                             │
│   ┌──────────────┐     ┌──────────────────┐                │
│   │  Store Twin   │────▶│  Live Telemetry   │               │
│   │  S-0001..0500 │     │  (Eventhouse)     │               │
│   └──────────────┘     └──────────────────┘                │
│         │                       ▲                           │
│         │                       │                           │
│   ┌──────────────┐     ┌──────────────────┐                │
│   │  Supply Chain │────▶│  Shipments Table  │               │
│   │  Twin         │     │  (Eventhouse)     │               │
│   └──────────────┘     └──────────────────┘                │
│                                                             │
│   ┌──────────────────────────────────────────┐             │
│   │  Simulation Engine                        │             │
│   │  • What-if scenarios                      │             │
│   │  • Capacity planning                      │             │
│   │  • Disruption modeling                    │             │
│   └──────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────┘
         │                        ▲
         ▼                        │
┌─────────────────┐    ┌──────────────────┐
│  Real-Time       │    │  IoT Simulator    │
│  Dashboards      │    │  OLTP Simulator   │
│  (KQL)           │    │  (streaming/)     │
└─────────────────┘    └──────────────────┘
```

---

## Step 1: Enable Digital Twin Builder (Preview)

1. Open the **Fabric portal** → **Settings** (gear icon) → **Admin portal**
2. Navigate to **Tenant settings** → **Digital Twin Builder (Preview)**
3. Enable the toggle for your tenant or specific security group
4. Wait 5–10 minutes for the feature to propagate

> **Note:** Digital Twin Builder is in Preview as of early 2025. Feature availability
> may vary by region and Fabric SKU.

---

## Step 2: Create a Digital Twin Space

1. Navigate to workspace **contoso-real-time-{environment}**
2. Click **+ New** → **Digital Twin Builder** (under Real-Time Intelligence)
3. Enter:
   - **Name:** `contoso_store_twin`
   - **Description:** `Digital twin of Contoso retail stores — physical layout, equipment, and live IoT telemetry`
4. Click **Create**

Repeat for the supply chain twin:
- **Name:** `contoso_supply_chain_twin`
- **Description:** `Digital twin of Contoso supply chain — suppliers, warehouses, distribution centers, and transport routes`

---

## Step 3: Define Entity Types (Store Twin)

Using the model in `store_twin_model.json`:

1. Open `contoso_store_twin` in the Digital Twin Builder canvas
2. For each entity type, click **+ Add entity type** and enter:

| Entity Type       | Properties (key fields)                          | Count (S-0001) |
|-------------------|--------------------------------------------------|----------------|
| Store             | StoreId, StoreName, StoreType, Capacity          | 1              |
| Department        | DepartmentId, DepartmentName, FloorArea          | 3–8            |
| Aisle             | AisleId, AisleName, Capacity                     | 5–20/dept      |
| Shelf             | ShelfId, ProductId, Capacity, CurrentLoad        | 4–10/aisle     |
| CheckoutLane      | LaneId, LaneType, OperationalStatus              | 8–20           |
| BackRoom          | BackRoomId, Capacity, Temperature                | 1–2            |
| HVACUnit          | UnitId, Temperature, TargetTemperature           | 2–6            |
| RefrigerationUnit | UnitId, Temperature, TargetTemperature           | 4–12           |

3. Define relationships by dragging connections between entity types:
   - Store → Department (composition, 1:N)
   - Department → Aisle (composition, 1:N)
   - Aisle → Shelf (composition, 1:N)
   - Store → CheckoutLane (composition, 1:N)
   - Store → BackRoom (composition, 1:N)
   - Store → HVACUnit (composition, 1:N)
   - Store → RefrigerationUnit (composition, 1:N)

---

## Step 4: Define Entity Types (Supply Chain Twin)

Using the model in `supply_chain_twin_model.json`:

1. Open `contoso_supply_chain_twin` in the Digital Twin Builder canvas
2. For each entity type, click **+ Add entity type**:

| Entity Type         | Properties (key fields)                             |
|---------------------|-----------------------------------------------------|
| Supplier            | SupplierId, SupplierName, Capacity, LeadTimeDays    |
| Warehouse           | WarehouseId, WarehouseName, Capacity, Utilization   |
| DistributionCenter  | CenterId, CenterName, ServiceRegion, Throughput     |
| TransportRoute      | RouteId, TransportMode, DistanceKm, AvgTransitDays  |
| Fleet               | FleetId, VehicleCount, ActiveVehicles, Utilization   |

3. Define relationships:
   - Supplier → Warehouse (association, N:M)
   - Warehouse → DistributionCenter (association, 1:N)
   - DistributionCenter → Store (association, 1:N, links to Store twin)
   - Fleet → TransportRoute (association, 1:N)

---

## Step 5: Link Live Telemetry from Eventhouse

### Store Twin — IoT Sensor Bindings

1. In `contoso_store_twin`, select the **HVACUnit** entity type
2. Click **+ Add telemetry binding**
3. Configure:
   - **Source:** KQL Database → `contoso_kqldb`
   - **Table:** `RealtimeIoT`
   - **Filter:** `SensorType == 'Temperature' and StoreId == '{StoreId}'`
   - **Value Column:** `ReadingValue`
   - **Timestamp Column:** `ReadingTimestamp`
   - **Refresh:** 15 seconds
4. Repeat for **Energy** sensor binding on HVACUnit
5. Bind **FootTraffic** sensor to the **Store** entity
6. Bind **RefrigerationUnit** to Temperature sensors (filter by DeviceId)

### Store Twin — POS Transaction Bindings

1. Select the **CheckoutLane** entity type
2. Click **+ Add telemetry binding**
3. Configure:
   - **Source:** KQL Database → `contoso_kqldb`
   - **Table:** `RealtimeSales`
   - **Filter:** `StoreId == '{StoreId}'`
   - **Value Column:** `TotalAmount`
   - **Timestamp Column:** `Timestamp`
   - **Refresh:** 10 seconds

### Supply Chain Twin — Shipment Bindings

1. In `contoso_supply_chain_twin`, select the **Supplier** entity
2. Add telemetry binding:
   - **Source:** `contoso_kqldb.Shipments`
   - **Filter:** `SupplierId == '{SupplierId}'`
   - **Value Column:** `Quantity`
   - **Timestamp Column:** `ShipmentDate`
3. Repeat for **Warehouse** (filter by `WarehouseId`, use `DeliveryDate`)
4. Bind **TransportRoute** to active shipment counts

---

## Step 6: Create Simulations

Digital Twin Builder supports what-if simulations. Create these scenarios:

### Simulation 1: Store HVAC Failure
- **Scenario:** HVAC unit goes offline in Store S-0001 during summer peak
- **Parameters:** Set HVACUnit.OperationalStatus = "fault", simulate temperature rise
- **Expected outcome:** Temperature crosses warning (28°C) then critical (32°C) thresholds
- **Action:** Validate that IoT alerts fire and reflex triggers activate

### Simulation 2: Supply Chain Disruption
- **Scenario:** Key supplier SUP-0001 goes to "suspended" status
- **Parameters:** Set Supplier.OperationalStatus = "suspended"
- **Expected outcome:** Downstream warehouses show increasing stockout risk
- **Action:** Identify alternative supplier routing via secondary routes

### Simulation 3: Holiday Demand Surge
- **Scenario:** 3x transaction volume during Black Friday / holiday season
- **Parameters:** Multiply Store.CurrentLoad by 3, CheckoutLane queue lengths increase
- **Expected outcome:** Identify capacity bottlenecks in checkout and HVAC
- **Action:** Pre-position staff and validate HVAC capacity

---

## Step 7: Validate the Twin

1. Verify entity counts match expectations:
   - 500 Store twins (one per physical store)
   - ~50 Supplier entities, ~20 Warehouse entities, ~8 Distribution Centers
2. Check telemetry bindings are live:
   ```kql
   // Verify IoT data flowing for twin binding
   RealtimeIoT
   | where ReadingTimestamp > ago(5m)
   | summarize DeviceCount = dcount(DeviceId) by SensorType
   ```
3. Open the 3D/2D visualization canvas and confirm entity relationships render correctly
4. Run a simulation and verify state propagation through the graph

---

## Terraform / IaC Status

> **As of January 2025, Digital Twin Builder does not have a Terraform resource**
> **or Fabric CLI command.** A placeholder module exists at
> `infra/modules/fabric-digital-twin/` ready for when the provider adds support.
>
> Current configuration must be done through the Fabric portal UI.
> See the placeholder module for tracked resource schema.

---

## Troubleshooting

| Symptom                             | Likely Cause                        | Resolution                            |
|-------------------------------------|-------------------------------------|---------------------------------------|
| Digital Twin Builder not in menu    | Preview not enabled for tenant      | Enable in Admin portal → Tenant settings |
| Telemetry not updating              | Eventhouse connection misconfigured | Verify KQL database connection string |
| Entity relationships not rendering  | Missing relationship definition     | Re-add relationships in the canvas    |
| Simulation not propagating changes  | Entity properties not bound         | Check telemetry bindings are active   |
| High latency on twin updates        | Refresh interval too aggressive     | Increase refresh from 10s to 30s      |
