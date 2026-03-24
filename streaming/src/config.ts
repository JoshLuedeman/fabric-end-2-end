import dotenv from "dotenv";

dotenv.config();

/**
 * Generates a sequential array of zero-padded IDs.
 * @param prefix - The prefix for each ID (e.g. "S-", "P-", "C-")
 * @param count - How many IDs to generate
 * @param padLength - Total digit length after the prefix
 * @returns Array of formatted IDs
 */
function generateIdRange(prefix: string, count: number, padLength: number): string[] {
  return Array.from({ length: count }, (_, i) =>
    `${prefix}${String(i + 1).padStart(padLength, "0")}`
  );
}

/** Application configuration loaded from environment variables with sensible defaults. */
export interface AppConfig {
  /** Event Hubs connection string. Required when DRY_RUN is false. */
  eventHubConnectionString: string;
  /** Event Hub name / topic. */
  eventHubName: string;
  /** When true, events are logged to the console instead of being sent to Event Hubs. */
  dryRun: boolean;
  /** Target POS transaction events per second. */
  posEventsPerSecond: number;
  /** Target IoT telemetry events per second. */
  iotEventsPerSecond: number;
  /** Target inventory update events per second. */
  inventoryEventsPerSecond: number;
  /** Available store IDs (S-001 … S-150). */
  storeIds: string[];
  /** Available product IDs (P-000001 … P-002000). */
  productIds: string[];
  /** Available customer IDs (C-000001 … C-050000). */
  customerIds: string[];
}

/**
 * Loads configuration from environment variables, falling back to defaults
 * where appropriate.  Throws if EVENT_HUB_CONNECTION_STRING is missing
 * while DRY_RUN is false.
 */
export function loadConfig(): AppConfig {
  const dryRun = (process.env["DRY_RUN"] ?? "true").toLowerCase() === "true";
  const eventHubConnectionString = process.env["EVENT_HUB_CONNECTION_STRING"] ?? "";

  if (!dryRun && !eventHubConnectionString) {
    throw new Error(
      "EVENT_HUB_CONNECTION_STRING is required when DRY_RUN is false"
    );
  }

  return {
    eventHubConnectionString,
    eventHubName: process.env["EVENT_HUB_NAME"] ?? "contoso-events",
    dryRun,
    posEventsPerSecond: parseInt(process.env["POS_EVENTS_PER_SECOND"] ?? "5", 10),
    iotEventsPerSecond: parseInt(process.env["IOT_EVENTS_PER_SECOND"] ?? "10", 10),
    inventoryEventsPerSecond: parseInt(process.env["INVENTORY_EVENTS_PER_SECOND"] ?? "2", 10),
    storeIds: generateIdRange("S-", 150, 3),
    productIds: generateIdRange("P-", 2000, 6),
    customerIds: generateIdRange("C-", 50000, 6),
  };
}
