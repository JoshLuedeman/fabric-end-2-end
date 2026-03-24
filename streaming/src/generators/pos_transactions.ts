import { v4 as uuidv4 } from "uuid";
import type { AppConfig } from "../config.js";

/** Point-of-sale transaction event emitted by store registers and online checkout. */
export interface POSEvent {
  eventType: "pos_transaction";
  transactionId: string;
  timestamp: string;
  storeId: string;
  customerId: string;
  productId: string;
  quantity: number;
  unitPrice: number;
  totalAmount: number;
  paymentMethod: string;
  channel: string;
}

const PAYMENT_METHODS = ["Credit Card", "Debit Card", "Cash", "Digital Wallet"] as const;
const CHANNELS = ["In-Store", "Online", "Mobile"] as const;

/**
 * Channel selection weights.
 * In-Store dominates during store hours; Online/Mobile are always available.
 */
const CHANNEL_WEIGHTS: Record<string, number> = {
  "In-Store": 0.65,
  "Online": 0.25,
  "Mobile": 0.10,
};

/**
 * Returns a time-of-day multiplier to simulate peak/off-peak traffic.
 * Peak periods: 11 am–2 pm (lunch) and 5 pm–8 pm (evening shopping).
 * @param hour - Current hour in 0–23 range
 */
function getTimeOfDayMultiplier(hour: number): number {
  if (hour >= 11 && hour < 14) return 2.0;   // lunch rush
  if (hour >= 17 && hour < 20) return 1.8;   // evening rush
  if (hour >= 9 && hour < 11) return 1.2;    // morning ramp-up
  if (hour >= 20 && hour < 22) return 1.0;   // winding down
  return 0.4;                                 // late night / early morning
}

/**
 * Returns a weekend multiplier (1.5× on Saturday/Sunday, 1× otherwise).
 * @param dayOfWeek - Day of week (0 = Sunday, 6 = Saturday)
 */
function getWeekendMultiplier(dayOfWeek: number): number {
  return dayOfWeek === 0 || dayOfWeek === 6 ? 1.5 : 1.0;
}

/**
 * Derives a deterministic but varied unit price from a product ID.
 * Prices range from roughly $0.99 to $199.99 to cover grocery-to-electronics spread.
 */
function getPriceForProduct(productId: string): number {
  const numericPart = parseInt(productId.replace("P-", ""), 10);
  const hash = ((numericPart * 2654435761) >>> 0) % 20000;
  const price = 0.99 + (hash / 100);
  return Math.round(price * 100) / 100;
}

/** Picks a random element from a readonly array. */
function pickRandom<T>(items: readonly T[]): T {
  return items[Math.floor(Math.random() * items.length)] as T;
}

/** Picks an element using weighted probability. */
function pickWeighted(weights: Record<string, number>): string {
  const entries = Object.entries(weights);
  const total = entries.reduce((sum, [, w]) => sum + w, 0);
  let roll = Math.random() * total;
  for (const [key, weight] of entries) {
    roll -= weight;
    if (roll <= 0) return key;
  }
  return entries[entries.length - 1]![0];
}

/**
 * Generates a single point-of-sale transaction event with realistic
 * variation based on time of day, day of week, and product catalogue.
 *
 * @param config - Application configuration providing ID pools
 * @returns A fully-populated POSEvent
 */
export function generatePOSEvent(config: AppConfig): POSEvent {
  const now = new Date();
  const storeId = pickRandom(config.storeIds);
  const customerId = pickRandom(config.customerIds);
  const productId = pickRandom(config.productIds);
  const quantity = Math.floor(Math.random() * 5) + 1;
  const unitPrice = getPriceForProduct(productId);
  const totalAmount = Math.round(unitPrice * quantity * 100) / 100;

  return {
    eventType: "pos_transaction",
    transactionId: uuidv4(),
    timestamp: now.toISOString(),
    storeId,
    customerId,
    productId,
    quantity,
    unitPrice,
    totalAmount,
    paymentMethod: pickRandom(PAYMENT_METHODS),
    channel: pickWeighted(CHANNEL_WEIGHTS),
  };
}

/**
 * Computes the effective events-per-second rate for POS transactions,
 * adjusting for time-of-day and weekend patterns.
 *
 * @param baseRate - Configured baseline events per second
 * @returns Adjusted events per second (never less than 1)
 */
export function getEffectivePOSRate(baseRate: number): number {
  const now = new Date();
  const multiplier =
    getTimeOfDayMultiplier(now.getHours()) * getWeekendMultiplier(now.getDay());
  return Math.max(1, Math.round(baseRate * multiplier));
}
