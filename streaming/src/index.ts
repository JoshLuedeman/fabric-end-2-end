import { EventHubProducerClient } from "@azure/event-hubs";
import { loadConfig } from "./config.js";
import type { AppConfig } from "./config.js";
import { generatePOSEvent, getEffectivePOSRate } from "./generators/pos_transactions.js";
import type { POSEvent } from "./generators/pos_transactions.js";
import { generateIoTEvent } from "./generators/iot_sensors.js";
import type { IoTEvent } from "./generators/iot_sensors.js";
import { generateInventoryEvent } from "./generators/inventory_updates.js";
import type { InventoryEvent } from "./generators/inventory_updates.js";

/** Union of all event types the generator can produce. */
type StreamEvent = POSEvent | IoTEvent | InventoryEvent;

/** Cumulative event counters for stats logging. */
interface EventCounters {
  pos: number;
  iot: number;
  inventory: number;
}

const counters: EventCounters = { pos: 0, iot: 0, inventory: 0 };

/** Handles for active intervals so we can clean up on shutdown. */
const activeIntervals: NodeJS.Timeout[] = [];

/** Optional Event Hub producer — only initialised when DRY_RUN is false. */
let producer: EventHubProducerClient | undefined;

/**
 * Sends or logs a batch of events depending on the current run mode.
 *
 * @param events - Array of events to dispatch
 * @param config - Application configuration
 */
async function dispatchEvents(events: StreamEvent[], config: AppConfig): Promise<void> {
  if (config.dryRun) {
    for (const event of events) {
      console.log(JSON.stringify(event));
    }
    return;
  }

  if (!producer) return;

  const batch = await producer.createBatch();
  for (const event of events) {
    const added = batch.tryAdd({ body: event });
    if (!added) {
      // Current batch is full — send it and start a new one
      await producer.sendBatch(batch);
      const newBatch = await producer.createBatch();
      if (!newBatch.tryAdd({ body: event })) {
        console.error("Event too large for a single batch:", event.eventType);
      }
    }
  }
  if (batch.count > 0) {
    await producer.sendBatch(batch);
  }
}

/**
 * Starts a recurring generator that produces events at the specified rate.
 *
 * @param name - Human-readable generator name for logging
 * @param rateProvider - Function returning current target events per second
 * @param generator - Function that produces a single event
 * @param counter - Key into the counters object
 * @param config - Application configuration
 */
function startGenerator(
  name: string,
  rateProvider: () => number,
  generator: () => StreamEvent,
  counter: keyof EventCounters,
  config: AppConfig,
): void {
  // Emit in 1-second ticks, producing `rate` events per tick
  const intervalId = setInterval(() => {
    const rate = rateProvider();
    const events: StreamEvent[] = [];
    for (let i = 0; i < rate; i++) {
      events.push(generator());
    }
    counters[counter] += events.length;
    dispatchEvents(events, config).catch((err: unknown) => {
      console.error(`[${name}] Failed to dispatch events:`, err);
    });
  }, 1000);

  activeIntervals.push(intervalId);
  console.log(`[${name}] Started — baseline ${rateProvider()} events/s`);
}

/**
 * Logs cumulative event counts every `intervalSeconds` seconds.
 * @param intervalSeconds - Seconds between each stats line
 */
function startStatsLogger(intervalSeconds: number): void {
  const intervalId = setInterval(() => {
    const total = counters.pos + counters.iot + counters.inventory;
    console.log(
      `[stats] POS: ${counters.pos} | IoT: ${counters.iot} | Inventory: ${counters.inventory} | Total: ${total}`,
    );
  }, intervalSeconds * 1000);

  activeIntervals.push(intervalId);
}

/**
 * Gracefully shuts down all generators and the Event Hub producer.
 * Called on SIGINT / SIGTERM.
 */
async function shutdown(): Promise<void> {
  console.log("\nShutting down generators…");

  for (const id of activeIntervals) {
    clearInterval(id);
  }

  if (producer) {
    console.log("Closing Event Hub connection…");
    await producer.close();
  }

  const total = counters.pos + counters.iot + counters.inventory;
  console.log(
    `Final counts — POS: ${counters.pos} | IoT: ${counters.iot} | Inventory: ${counters.inventory} | Total: ${total}`,
  );

  process.exit(0);
}

/**
 * Main entry point.
 * Loads configuration, optionally connects to Event Hubs, starts all three
 * generators, and waits for a shutdown signal.
 */
async function main(): Promise<void> {
  const config = loadConfig();

  console.log("=== Contoso Event Generator ===");
  console.log(`Mode: ${config.dryRun ? "DRY RUN (console only)" : "LIVE (sending to Event Hubs)"}`);
  console.log(`Rates — POS: ${config.posEventsPerSecond}/s | IoT: ${config.iotEventsPerSecond}/s | Inventory: ${config.inventoryEventsPerSecond}/s`);
  console.log(`Stores: ${config.storeIds.length} | Products: ${config.productIds.length} | Customers: ${config.customerIds.length}`);

  if (!config.dryRun) {
    producer = new EventHubProducerClient(
      config.eventHubConnectionString,
      config.eventHubName,
    );
    console.log(`Connected to Event Hub: ${config.eventHubName}`);
  }

  // Register shutdown handlers
  process.on("SIGINT", () => void shutdown());
  process.on("SIGTERM", () => void shutdown());

  // Start generators
  startGenerator(
    "POS Transactions",
    () => getEffectivePOSRate(config.posEventsPerSecond),
    () => generatePOSEvent(config),
    "pos",
    config,
  );

  startGenerator(
    "IoT Sensors",
    () => config.iotEventsPerSecond,
    () => generateIoTEvent(config),
    "iot",
    config,
  );

  startGenerator(
    "Inventory Updates",
    () => config.inventoryEventsPerSecond,
    () => generateInventoryEvent(config),
    "inventory",
    config,
  );

  // Log stats every 10 seconds
  startStatsLogger(10);

  console.log("\nGenerators running. Press Ctrl+C to stop.\n");
}

main().catch((err: unknown) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
