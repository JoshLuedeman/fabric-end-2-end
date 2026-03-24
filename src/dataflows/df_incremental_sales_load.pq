// ---------------------------------------------------------------------------
// Dataflow Gen2: Incremental Sales Load
// Watermark-based incremental load of sales transactions from the bronze
// (staging) lakehouse to the silver lakehouse. Uses modified_at timestamp
// as the high-watermark to process only new/updated records.
// ---------------------------------------------------------------------------

section IncrementalSalesLoad;

shared IncrementalSalesLoad = let
    // Step 1: Read the current high-watermark from silver control table
    SilverSource = Lakehouse.Contents(null){[workspaceId = "{{ .WORKSPACE_ID }}"]}[Data]{[lakehouseId = "{{ .SILVER_LAKEHOUSE_ID }}"]}[Data],
    WatermarkTable = try SilverSource{[Name = "load_watermarks"]}[Data] otherwise #table({"table_name", "last_watermark"}, {}),
    CurrentWatermark = try Record.Field(Table.First(Table.SelectRows(WatermarkTable, each [table_name] = "sales_transactions")), "last_watermark")
                       otherwise #datetime(2020, 1, 1, 0, 0, 0),

    // Step 2: Connect to bronze lakehouse and read new records
    BronzeSource = Lakehouse.Contents(null){[workspaceId = "{{ .WORKSPACE_ID }}"]}[Data]{[lakehouseId = "{{ .BRONZE_LAKEHOUSE_ID }}"]}[Data],
    Sales_Raw = BronzeSource{[Name = "raw_sales_transactions"]}[Data],

    // Step 3: Filter to records newer than the watermark
    IncrementalRows = Table.SelectRows(Sales_Raw, each [modified_at] > CurrentWatermark),

    // Step 4: Apply silver-layer transformations
    Typed = Table.TransformColumnTypes(IncrementalRows, {
        {"transaction_id",   type text},
        {"store_id",         type text},
        {"customer_id",      type text},
        {"product_id",       type text},
        {"quantity",         Int64.Type},
        {"unit_price",       type number},
        {"discount_amount",  type number},
        {"transaction_date", type datetime},
        {"modified_at",      type datetime}
    }),

    // Step 5: Compute derived columns
    WithLineTotal = Table.AddColumn(Typed, "line_total", each [quantity] * [unit_price] - ([discount_amount] ?? 0), type number),
    WithNetAmount = Table.AddColumn(WithLineTotal, "net_amount", each Number.Round([line_total], 2), type number),

    // Step 6: Add load metadata
    WithLoadMeta = Table.AddColumn(WithNetAmount, "loaded_at", each DateTime.LocalNow(), type datetime),
    Final = Table.AddColumn(WithLoadMeta, "load_batch_id", each Text.From(DateTime.LocalNow()) & "_incremental", type text)
in
    Final;
