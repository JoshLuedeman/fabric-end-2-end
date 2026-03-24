import { v4 as uuidv4 } from "uuid";
import type { AppConfig } from "../config.js";

/** IoT sensor telemetry event from in-store devices. */
export interface IoTEvent {
  eventType: "iot_telemetry";
  readingId: string;
  timestamp: string;
  deviceId: string;
  storeId: string;
  sensorType: string;
  value: number;
  unit: string;
  status: string;
}

/** Supported sensor types with their normal ranges and units. */
interface SensorProfile {
  type: string;
  unit: string;
  normalMin: number;
  normalMax: number;
  warningThreshold: number;
  criticalThreshold: number;
  /** Number of devices of this type per store. */
  devicesPerStore: number;
}

const SENSOR_PROFILES: readonly SensorProfile[] = [
  {
    type: "Temperature",
    unit: "°C",
    normalMin: 18,
    normalMax: 24,
    warningThreshold: 28,
    criticalThreshold: 32,
    devicesPerStore: 4,
  },
  {
    type: "Humidity",
    unit: "%",
    normalMin: 40,
    normalMax: 60,
    warningThreshold: 70,
    criticalThreshold: 80,
    devicesPerStore: 2,
  },
  {
    type: "FootTraffic",
    unit: "persons/min",
    normalMin: 0,
    normalMax: 30,
    warningThreshold: 50,
    criticalThreshold: 80,
    devicesPerStore: 2,
  },
  {
    type: "Energy",
    unit: "kW",
    normalMin: 10,
    normalMax: 50,
    warningThreshold: 70,
    criticalThreshold: 90,
    devicesPerStore: 1,
  },
  {
    type: "DoorCounter",
    unit: "events/min",
    normalMin: 0,
    normalMax: 20,
    warningThreshold: 40,
    criticalThreshold: 60,
    devicesPerStore: 2,
  },
] as const;

/** Target anomaly rate – roughly 2 % of readings will be Warning or Critical. */
const ANOMALY_RATE = 0.02;

/** Picks a random element from a readonly array. */
function pickRandom<T>(items: readonly T[]): T {
  return items[Math.floor(Math.random() * items.length)] as T;
}

/**
 * Returns a foot-traffic multiplier that peaks during business hours.
 * @param hour - Current hour (0–23)
 */
function getFootTrafficMultiplier(hour: number): number {
  if (hour >= 10 && hour < 14) return 1.8;
  if (hour >= 14 && hour < 17) return 1.2;
  if (hour >= 17 && hour < 20) return 1.6;
  if (hour >= 8 && hour < 10) return 0.8;
  return 0.2;
}

/**
 * Generates a sensor reading value, occasionally injecting anomalies.
 * Normal readings fall within [normalMin, normalMax].
 * Anomalous readings exceed the warning or critical threshold.
 *
 * @param profile - Sensor specification
 * @param hour - Current hour for time-based adjustments
 * @returns Tuple of [value, status]
 */
function generateReading(profile: SensorProfile, hour: number): [number, string] {
  const isAnomaly = Math.random() < ANOMALY_RATE;

  if (isAnomaly) {
    const isCritical = Math.random() < 0.3;
    const threshold = isCritical ? profile.criticalThreshold : profile.warningThreshold;
    const overshoot = Math.random() * (profile.criticalThreshold - profile.warningThreshold + 5);
    const value = Math.round((threshold + overshoot) * 100) / 100;
    return [value, isCritical ? "Critical" : "Warning"];
  }

  let min = profile.normalMin;
  let max = profile.normalMax;

  // Adjust foot-traffic and door-counter sensors by time of day
  if (profile.type === "FootTraffic" || profile.type === "DoorCounter") {
    const multiplier = getFootTrafficMultiplier(hour);
    max = Math.round(max * multiplier);
    min = Math.round(min * multiplier);
  }

  // Energy: baseline load varies with occupancy
  if (profile.type === "Energy") {
    const load = getFootTrafficMultiplier(hour);
    min = Math.round(profile.normalMin * (0.5 + load * 0.3));
    max = Math.round(profile.normalMax * (0.5 + load * 0.5));
  }

  const value = Math.round((min + Math.random() * (max - min)) * 100) / 100;
  return [value, "Normal"];
}

/**
 * Generates a single IoT sensor telemetry event from a random sensor type
 * and store, with realistic values and occasional anomalies (~2 % rate).
 *
 * @param config - Application configuration providing store IDs
 * @returns A fully-populated IoTEvent
 */
export function generateIoTEvent(config: AppConfig): IoTEvent {
  const now = new Date();
  const hour = now.getHours();
  const storeId = pickRandom(config.storeIds);
  const profile = pickRandom(SENSOR_PROFILES);
  const deviceIndex = Math.floor(Math.random() * profile.devicesPerStore) + 1;
  const deviceId = `IOT-${storeId}-${profile.type}-${deviceIndex}`;

  const [value, status] = generateReading(profile, hour);

  return {
    eventType: "iot_telemetry",
    readingId: uuidv4(),
    timestamp: now.toISOString(),
    deviceId,
    storeId,
    sensorType: profile.type,
    value,
    unit: profile.unit,
    status,
  };
}
