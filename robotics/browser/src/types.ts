/**
 * Core types for the ontology-driven robot simulation.
 * These mirror the Python dataclasses in robot_simulation.py
 */

export interface Position {
  x: number;
  y: number;
}

export function distance(a: Position, b: Position): number {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
}

export interface WorldObject {
  id: string;
  position: Position;
  value: number;
  collected: boolean;
}

export interface Obstacle {
  id: string;
  position: Position;
  radius: number;
}

export interface Pheromone {
  position: Position;
  type: PheromoneType;
  strength: number;
  depositedBy: string;
  tickDeposited: number;
}

export enum PheromoneType {
  EXPLORATION = "exploration",
  OBJECT_FOUND = "object_found",
  DANGER = "danger",
  OBJECT_COLLECTED = "object_collected",
}

export const PHEROMONE_CONFIG: Record<PheromoneType, { decayRate: number; depositInterval: number; initialStrength: number }> = {
  [PheromoneType.EXPLORATION]: { decayRate: 0.02, depositInterval: 2, initialStrength: 1.0 },
  [PheromoneType.OBJECT_FOUND]: { decayRate: 0.01, depositInterval: 1, initialStrength: 1.0 },
  [PheromoneType.DANGER]: { decayRate: 0.05, depositInterval: 1, initialStrength: 1.0 },
  [PheromoneType.OBJECT_COLLECTED]: { decayRate: 0.03, depositInterval: 1, initialStrength: 1.0 },
};

export const ROBOT_COLORS = [
  "#3498db", // Blue
  "#e74c3c", // Red
  "#2ecc71", // Green
  "#9b59b6", // Purple
  "#f39c12", // Orange
  "#1abc9c", // Teal
];

export interface RobotState {
  // Sensor data
  collision: boolean;
  battery: number;
  distanceToNearest: number;
  distanceToObstacle: number;
  pathBlocked: boolean;

  // Inferred states (from rules)
  atObject: boolean;
  nearObject: boolean;
  lowBattery: boolean;
  mustAvoid: boolean;
  emergencyAvoid: boolean;
  inLoop: boolean;

  // Geometric metrics
  coverageArea: number;
  pathKnottiness: number;
  recentPositionCount: number;

  // Venture/escape states
  smallCoverage: boolean;
  shouldVenture: boolean;
  severelyCircling: boolean;
}

export interface AvoidanceInfo {
  mustAvoid: boolean;
  avoidLeft: boolean;
  avoidRight: boolean;
  clearPathAngle: number;
  emergencyAvoid: boolean;
  inLoop: boolean;
  stuckCounter: number;
  escapeMode: boolean;
  escapeTicks: number;
  coverageArea: number;
}
