import { v4 as uuidv4 } from "uuid";
import type { AppConfig } from "../config.js";

/** Inventory movement event tracking stock changes at a store/product level. */
export interface InventoryEvent {
  eventType: "inventory_update";
  eventId: string;
  timestamp: string;
  productId: string;
  storeId: string;
  movementType: string;
  quantity: number;
  previousOnHand: number;
  currentOnHand: number;
}

const MOVEMENT_TYPES = ["Sale", "Receipt", "Transfer", "Adjustment"] as const;

/**
 * Weighted distribution of movement types.
 * Sales dominate day-to-day movements; receipts and transfers are less frequent.
 */
const MOVEMENT_WEIGHTS: Record<string, number> = {
  Sale: 0.55,
  Receipt: 0.25,
  Transfer: 0.12,
  Adjustment: 0.08,
};

/**
 * Simulated on-hand stock levels keyed by "storeId:productId".
 * Lazily initialised on first access with a random starting quantity.
 */
const stockLevels = new Map<string, number>();

/** Picks a random element from a readonly array. */
function pickRandom<T>(items: readonly T[]): T {
  return items[Math.floor(Math.random() * items.length)] as T;
}

/** Selects a movement type using weighted probability. */
function pickWeightedMovement(): string {
  const entries = Object.entries(MOVEMENT_WEIGHTS);
  const total = entries.reduce((sum, [, w]) => sum + w, 0);
  let roll = Math.random() * total;
  for (const [key, weight] of entries) {
    roll -= weight;
    if (roll <= 0) return key;
  }
  return entries[entries.length - 1]![0];
}

/**
 * Returns the current on-hand quantity for a store/product pair,
 * initialising it with a random value (50–500) on first access.
 *
 * @param key - Composite key in the form "storeId:productId"
 */
function getStockLevel(key: string): number {
  if (!stockLevels.has(key)) {
    stockLevels.set(key, Math.floor(Math.random() * 451) + 50);
  }
  return stockLevels.get(key)!;
}

/**
 * Computes the movement quantity and direction based on the movement type.
 * Sales and Transfers reduce stock; Receipts and Adjustments can increase it.
 *
 * @param movementType - One of Sale, Receipt, Transfer, Adjustment
 * @param currentOnHand - Current stock level
 * @returns Signed quantity (negative for decreases)
 */
function computeQuantityDelta(movementType: string, currentOnHand: number): number {
  switch (movementType) {
    case "Sale": {
      const max = Math.min(5, currentOnHand);
      return max > 0 ? -(Math.floor(Math.random() * max) + 1) : 0;
    }
    case "Receipt":
      return Math.floor(Math.random() * 96) + 5; // 5–100 units
    case "Transfer": {
      // Could be inbound or outbound
      const isInbound = Math.random() < 0.4;
      if (isInbound) return Math.floor(Math.random() * 46) + 5; // 5–50
      const maxOut = Math.min(20, currentOnHand);
      return maxOut > 0 ? -(Math.floor(Math.random() * maxOut) + 1) : 0;
    }
    case "Adjustment": {
      // Small correction in either direction
      const delta = Math.floor(Math.random() * 11) - 5; // -5 to +5
      if (currentOnHand + delta < 0) return 0;
      return delta;
    }
    default:
      return 0;
  }
}

/**
 * Generates a single inventory movement event with realistic stock-level
 * tracking.  Stock levels are maintained in-memory across calls so that
 * previousOnHand / currentOnHand values stay consistent.
 *
 * @param config - Application configuration providing store and product ID pools
 * @returns A fully-populated InventoryEvent
 */
export function generateInventoryEvent(config: AppConfig): InventoryEvent {
  const now = new Date();
  const storeId = pickRandom(config.storeIds);
  const productId = pickRandom(config.productIds);
  const key = `${storeId}:${productId}`;
  const movementType = pickWeightedMovement();

  const previousOnHand = getStockLevel(key);
  const delta = computeQuantityDelta(movementType, previousOnHand);
  const currentOnHand = Math.max(0, previousOnHand + delta);

  stockLevels.set(key, currentOnHand);

  return {
    eventType: "inventory_update",
    eventId: uuidv4(),
    timestamp: now.toISOString(),
    productId,
    storeId,
    movementType,
    quantity: Math.abs(delta),
    previousOnHand,
    currentOnHand,
  };
}
