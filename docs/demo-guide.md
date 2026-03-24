# Demo Guide

A step-by-step walkthrough of **Tales & Timber** — a living, breathing data platform running on Microsoft Fabric. This isn't a slide deck; it's a real company's data infrastructure. Every screen you open has millions of rows behind it, every pipeline has run, and every alert can fire.

## Prerequisites

1. Azure subscription with Fabric capacity provisioned (set `FABRIC_SKU` variable — default F8)
2. Service principal configured (see `infra/bootstrap/README.md`)
3. GitHub repository secrets configured for OIDC auth
4. Tools installed: Terraform, Python 3.12+, Node.js 22+, Fabric CLI
5. Event generator started at least 5 minutes before the real-time acts

## Demo Flow

---

### Act 1: The Operational Backbone (5-7 min)

**Story**: *"Before analytics, before AI, there's a cash register. Let's start where every data story begins — the transaction."*

#### 1.1 The POS System — Fabric SQL Database

Open the Fabric SQL Database. This is Tales & Timber's operational point-of-sale system — a normalized 3NF OLTP database that processes every sale across 500 stores in 8 countries.

- Show the schema: `customers`, `products`, `stores`, `transactions`, `transaction_items` — classic retail OLTP
- Run `EXEC sp_process_sale` — walk through what happens when a cashier scans an item:
  - Insert into `transactions` → insert line items → update inventory → calculate loyalty points
  - This is a real ACID transaction, running in Fabric SQL Database

#### 1.2 Change Data Capture

Show the CDC watermark table. Point out the `last_extracted_at` timestamps ticking forward.

- "Every time a sale completes, CDC captures the change. This is the heartbeat of Tales & Timber's 500 stores — and it's what feeds the entire analytics platform downstream."

#### 1.3 The Scale

- 2M customers, 25K products, 500 stores, 15K employees
- "This database processes thousands of transactions per hour. Let's follow that data into the lakehouse."

---

### Act 2: The Data Platform (5-7 min)

**Story**: *"Raw transactions aren't useful to anyone. Tales & Timber's data engineering team transforms noise into signal through a three-layer lakehouse."*

#### 2.1 Metadata-Driven Ingestion

Open the pipeline configuration table. Show how ingestion is config-driven — new source tables are onboarded by adding a row, not by writing new pipelines.

- "One pipeline handles all ingestion. The config table tells it what to extract, where to land it, and how to handle schema changes. That's how you scale to dozens of sources without drowning in pipeline spaghetti."

#### 2.2 Medallion Architecture

Walk through the three layers:

- **Bronze**: Raw CDC extracts, partitioned by date, schema-on-read. Show the raw Parquet files landing from the OLTP database.
- **Silver**: Cleansed, deduplicated, business-typed. Show `transform_sales.py` — null handling, type casting, derived columns like `is_weekend`, `fiscal_quarter`.
- **Gold**: Star schema fact and dimension tables. Show `fact_sales.py` — surrogate key assignment, slowly changing dimensions, aggregation-ready output.

#### 2.3 Apache Airflow Orchestration

Open the Airflow DAG view. Show the three DAGs:

- **Daily ETL** (`dag_daily_etl`): Full bronze → silver → gold refresh, runs at 2 AM UTC
- **Hourly Quality** (`dag_hourly_quality`): Data quality checks, freshness monitoring, row count validation
- **Weekly Maintenance** (`dag_weekly_maintenance`): Table optimization, orphan file cleanup, statistics refresh

"200M+ sales transactions have flowed through this pipeline. Every transaction from every store, every day."

---

### Act 3: The Warehouse & Analytics (5-7 min)

**Story**: *"The CFO doesn't read Parquet files. She needs a dashboard she can trust, with data she can drill into."*

#### 3.1 Star Schema Warehouse

Open the Fabric Warehouse. Show the star schema:

- `dim_customer`, `dim_product`, `dim_store`, `dim_date`, `dim_employee`
- `fact_sales`, `fact_inventory`, `fact_shipments`
- Hundreds of millions of rows, queryable via T-SQL

Run `vw_sales_summary` — show aggregated revenue by region, category, and time period.

#### 3.2 Power BI Executive Dashboard

Open the Executive Dashboard. This is what Tales & Timber's leadership team sees every morning:

- **Revenue trends**: YoY and MoM comparisons across 8 countries
- **Regional performance**: Map visualization with drill-through to store-level detail
- **Product mix**: Category contribution analysis, margin by product line
- **KPIs**: Revenue, transactions, average basket size, customer retention rate

Click into a region → drill through to individual store performance. "The CFO sees this every morning. She can go from global trends to a single store in two clicks."

#### 3.3 OneLake Security

Demonstrate row-level security — switch user context to show how a regional manager sees only their territory. Show column-level security hiding PII from analyst roles.

---

### Act 4: Real-Time Intelligence (5-7 min)

**Story**: *"When a refrigerator fails in Store 247 at 2 AM, Tales & Timber can't wait for tomorrow's batch report. They need to know now."*

#### 4.1 Streaming Events

Show the event generator pushing three streams simultaneously:

```bash
make stream-run
```

- **POS Transactions**: 5 events/sec — live sales from stores worldwide
- **IoT Sensors**: 10 events/sec — temperature, humidity, power, foot traffic
- **Inventory Updates**: 2 events/sec — stock movements, restocking events

#### 4.2 Eventhouse & KQL

Open the Eventhouse KQL dashboard. Show data updating in real time:

- Run `sales_anomaly_detection.kql` — show the 3σ deviation algorithm flagging unusual patterns
- Run `iot_device_health.kql` — show a sensor that has stopped reporting (simulated failure)
- Show the time-series visualizations updating live

#### 4.3 Data Activator Alerts

Show the Reflex triggers firing:

- **IoT Failure Alert**: A sensor goes silent for > 5 minutes → Power Automate creates an incident ticket and pages the facilities team
- **Sales Anomaly Alert**: A store's sales deviate > 3σ from its rolling average → Teams notification to the regional manager

"When something goes wrong, Tales & Timber knows in minutes, not days."

---

### Act 5: AI & Data Science (5-7 min)

**Story**: *"Reporting on the past is table stakes. Tales & Timber's data science team predicts the future and automates the response."*

#### 5.1 Customer Segmentation

Open the segmentation notebook. Show the RFM (Recency, Frequency, Monetary) analysis across 2M customers, clustered into segments via K-Means:

- Champions, Loyal Customers, At Risk, Lost
- Show the cluster visualization — clear separation between high-value and churning customers

#### 5.2 Churn Prediction

Walk through the LightGBM churn model:

- Show the MLflow experiment — 5 tracked runs with hyperparameter tuning
- Pull up a specific VIP customer flagged at high churn risk (probability > 0.85)
- Show the **Churn Risk Alert** (Data Activator) — when a VIP customer's churn probability crosses the threshold, a Reflex trigger sends an email to the retention team with the customer profile and recommended action

"This customer spent $12,000 last year and hasn't been back in 6 weeks. The retention team got an alert this morning."

#### 5.3 Demand Forecasting

Show the Prophet time-series model predicting next month's sales per store × category:

- Show the forecast vs actuals for a specific store — the model captures seasonality, trends, and holiday effects
- "This feeds directly into the inventory replenishment engine. Tales & Timber orders what they'll need, not what they think they'll need."

#### 5.4 More ML Capabilities

Briefly show:

- **Promotion Effectiveness**: Propensity score matching to measure causal impact of promotions — not just correlation, but "did the promotion actually cause the lift?"
- **Anomaly Detection (ML)**: Isolation Forest running on sales and inventory data, catching subtle patterns that rule-based alerts miss

---

### Act 6: The Platform Story (5-7 min)

**Story**: *"Everything you've seen — the OLTP database, the lakehouse, the warehouse, the real-time engine, the ML models, the alerts — is deployed from code and managed as a platform."*

#### 6.1 Graph in Fabric

Open the supply chain graph model. Run a GQL query:

- "Find the shortest supply path from Supplier SUP-042 to Store S-015"
- Visualize the supplier → warehouse → distribution center → store relationships
- "Graph lets Tales & Timber reason about their supply chain as a network, not a collection of tables."

#### 6.2 Data Agents

Open the **Sales Analyst** agent:

- Ask: "What were total sales last quarter by region?"
- Ask: "Why did sales drop in the South region last week?"

Open the **Supply Chain Advisor** agent:

- Ask: "Which suppliers have delivery issues?"
- "Natural language access to the entire data platform. No SQL required."

#### 6.3 Infrastructure as Code

Show the Terraform modules:

- `infra/environments/dev/main.tf` — declarative workspace layout, 8 workspaces
- Composable modules: capacity, workspace, lakehouse, warehouse, eventhouse, SQL database
- `terraform plan` output — the entire platform diffable and reviewable

#### 6.4 CI/CD & Automation

Show the GitHub Actions workflows:

- `deploy-infra.yml` — Terraform with approval gates
- `deploy-content.yml` — Fabric CLI deploying notebooks, reports, KQL scripts
- `generate-data.yml` — synthetic data generation at scale
- `deploy-streaming.yml` — event generator deployment

#### 6.5 Branched Workspaces

Show the feature branching workflow:

- Create a branch workspace → make changes → diff → merge
- "This isn't just analytics. It's a complete data platform — automated, governed, and version-controlled."

---

## Presenter Tips

- **Pacing**: Keep each act to 5-7 minutes for a 30-40 minute total demo. Adjust depth based on audience.
- **Opening**: Start with Act 1 (OLTP) to ground the audience in "real business." The cash register is universally understood.
- **The money moment**: The transition from real-time alert (Act 4) → ML prediction (Act 5) → automated action (Reflex alert) is the most powerful sequence. Practice this transition.
- **Business audiences**: Spend more time in Acts 1, 3, and 5. Skip Airflow details, emphasize dashboards and predictions.
- **Technical audiences**: Go deeper in Acts 2 and 6. Show the Terraform modules, the Airflow DAGs, the MLflow experiment tracking.
- **Closing**: Always end with Act 6 (Platform Story) to differentiate from competitors. Anyone can show a dashboard. Not everyone can show the entire platform deployed from a `git push`.
- **Data scale**: Mention the numbers — 532M+ rows, ~40GB, 200M sales transactions. Scale makes the demo credible.
- **Fallback**: If real-time streaming hiccups, pivot to the historical KQL data already in the Eventhouse. The queries still work.
