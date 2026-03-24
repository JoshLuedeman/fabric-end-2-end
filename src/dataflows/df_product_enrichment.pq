// ---------------------------------------------------------------------------
// Dataflow Gen2: Product Enrichment
// Enriches the product catalog with computed columns: margin percentage,
// category rollup hierarchy, and seasonal demand flags.
// ---------------------------------------------------------------------------

section ProductEnrichment;

shared ProductEnrichment = let
    // Step 1: Connect to bronze lakehouse product table
    Source = Lakehouse.Contents(null){[workspaceId = "{{ .WORKSPACE_ID }}"]}[Data]{[lakehouseId = "{{ .BRONZE_LAKEHOUSE_ID }}"]}[Data],
    Products_Raw = Source{[Name = "raw_products"]}[Data],

    // Step 2: Compute margin percentage
    WithMargin = Table.AddColumn(Products_Raw, "margin_pct", each
        if [cost_price] = null or [cost_price] = 0 then null
        else Number.Round(([retail_price] - [cost_price]) / [retail_price] * 100, 2),
        type number
    ),

    // Step 3: Category rollup (department > category > subcategory)
    WithRollup = Table.AddColumn(WithMargin, "category_rollup", each
        Text.Combine({[department], [category], [subcategory]}, " > "),
        type text
    ),

    // Step 4: Margin tier classification
    WithMarginTier = Table.AddColumn(WithRollup, "margin_tier", each
        if [margin_pct] = null then "Unknown"
        else if [margin_pct] >= 60 then "Premium"
        else if [margin_pct] >= 40 then "Standard"
        else if [margin_pct] >= 20 then "Value"
        else "Low-Margin",
        type text
    ),

    // Step 5: Seasonal flags based on product attributes
    WithSeasonalFlags = Table.AddColumn(WithMarginTier, "seasonal_flags", each
        let
            cat = Text.Lower([category] ?? ""),
            sub = Text.Lower([subcategory] ?? ""),
            flags = List.Select({
                if Text.Contains(cat, "outdoor") or Text.Contains(sub, "summer") or Text.Contains(sub, "swim") then "Summer" else null,
                if Text.Contains(cat, "winter") or Text.Contains(sub, "ski") or Text.Contains(sub, "holiday") then "Winter" else null,
                if Text.Contains(sub, "school") or Text.Contains(sub, "backpack") then "Back-to-School" else null,
                if Text.Contains(sub, "gift") or Text.Contains(sub, "holiday") or Text.Contains(sub, "christmas") then "Holiday" else null
            }, each _ <> null)
        in
            if List.Count(flags) = 0 then "Year-Round"
            else Text.Combine(flags, ", "),
        type text
    ),

    // Step 6: Add enrichment metadata
    WithMetadata = Table.AddColumn(WithSeasonalFlags, "enriched_at", each DateTime.LocalNow(), type datetime),
    Final = Table.AddColumn(WithMetadata, "enrichment_version", each "1.0", type text)
in
    Final;
