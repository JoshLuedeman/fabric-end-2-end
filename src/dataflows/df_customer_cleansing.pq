// ---------------------------------------------------------------------------
// Dataflow Gen2: Customer Cleansing
// Power Query M expression that deduplicates customer records, standardizes
// addresses, and normalizes phone numbers from the bronze customer table.
// ---------------------------------------------------------------------------

section CustomerCleansing;

shared CustomerCleansing = let
    // Step 1: Connect to bronze lakehouse customer table
    Source = Lakehouse.Contents(null){[workspaceId = "{{ .WORKSPACE_ID }}"]}[Data]{[lakehouseId = "{{ .BRONZE_LAKEHOUSE_ID }}"]}[Data],
    Customers_Raw = Source{[Name = "raw_customers"]}[Data],

    // Step 2: Remove exact duplicate rows
    Deduplicated = Table.Distinct(Customers_Raw, {"email", "first_name", "last_name"}),

    // Step 3: Standardize address fields
    StandardizedAddress = Table.TransformColumns(Deduplicated, {
        {"street_address", each Text.Trim(Text.Clean(_)), type text},
        {"city",           each Text.Proper(Text.Trim(_)), type text},
        {"state",          each Text.Upper(Text.Trim(_)), type text},
        {"postal_code",    each Text.PadStart(Text.Trim(_), 5, "0"), type text},
        {"country",        each if _ = null or _ = "" then "US" else Text.Upper(Text.Trim(_)), type text}
    }),

    // Step 4: Normalize phone numbers to E.164 format (+1XXXXXXXXXX)
    NormalizedPhone = Table.TransformColumns(StandardizedAddress, {
        {"phone_number", each
            let
                digitsOnly = Text.Select(_, {"0".."9"}),
                normalized = if Text.Length(digitsOnly) = 10 then "+1" & digitsOnly
                             else if Text.Length(digitsOnly) = 11 and Text.Start(digitsOnly, 1) = "1" then "+" & digitsOnly
                             else digitsOnly
            in normalized, type text}
    }),

    // Step 5: Standardize email to lowercase
    NormalizedEmail = Table.TransformColumns(NormalizedPhone, {
        {"email", each Text.Lower(Text.Trim(_)), type text}
    }),

    // Step 6: Add cleansing metadata
    WithMetadata = Table.AddColumn(NormalizedEmail, "cleansed_at", each DateTime.LocalNow(), type datetime),
    Final = Table.AddColumn(WithMetadata, "cleansing_version", each "1.0", type text)
in
    Final;
