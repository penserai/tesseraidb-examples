/**
 * Robot class with state management and movement logic.
 */

import { Position, distance, ROBOT_COLORS } from "./types";

export class Robot {
  id: string;
  position: Position;
  heading: number;
  speed: number;
  sensorRange: number;
  battery: number;
  batteryCapacity: number;
  isActive: boolean;
  robotIndex: number;
  color: string;

  // Collision state
  hasCollision: boolean = false;
  hasRobotCollision: boolean = false;
  collisionCount: number = 0;
  robotCollisionCount: number = 0;

  // Movement tracking
  distanceTraveled: number = 0;
  objectsCollected: number = 0;
  successMetric: number = 0;
  tickCount: number = 0;
  currentAction: string = "Idle";

  // Stuck detection
  lastPosition: Position;
  ticksWithoutMovement: number = 0;
  isStuck: boolean = false;
  escapeHeading: number | null = null;

  // Wanderlust (exploration drive)
  wanderlust: number = 0;
  ticksSinceDiscovery: number = 0;
  ticksInCluster: number = 0;

  constructor(
    id: string,
    position: Position,
    heading: number = 0,
    robotIndex: number = 0,
    speed: number = 1.0,
    sensorRange: number = 3.0,
    battery: number = 100,
    batteryCapacity: number = 100
  ) {
    this.id = id;
    this.position = { ...position };
    this.heading = heading;
    this.speed = speed;
    this.sensorRange = sensorRange;
    this.battery = battery;
    this.batteryCapacity = batteryCapacity;
    this.isActive = true;
    this.robotIndex = robotIndex;
    this.color = ROBOT_COLORS[robotIndex % ROBOT_COLORS.length];
    this.lastPosition = { ...position };
  }

  move(dx: number, dy: number, worldWidth: number, worldHeight: number): void {
    const newX = Math.max(0.5, Math.min(worldWidth - 0.5, this.position.x + dx));
    const newY = Math.max(0.5, Math.min(worldHeight - 0.5, this.position.y + dy));

    const dist = distance(this.position, { x: newX, y: newY });
    this.distanceTraveled += dist;

    this.position.x = newX;
    this.position.y = newY;

    // Update heading based on movement
    if (Math.abs(dx) > 0.01 || Math.abs(dy) > 0.01) {
      this.heading = (Math.atan2(dy, dx) * 180) / Math.PI;
    }
  }

  moveForward(worldWidth: number, worldHeight: number): void {
    const rad = (this.heading * Math.PI) / 180;
    const dx = Math.cos(rad) * this.speed;
    const dy = Math.sin(rad) * this.speed;
    this.move(dx, dy, worldWidth, worldHeight);
  }

  turnTo(targetHeading: number): void {
    // Normalize to 0-360
    this.heading = ((targetHeading % 360) + 360) % 360;
  }

  turnToward(target: Position, turnRate: number = 15): void {
    const targetAngle = (Math.atan2(target.y - this.position.y, target.x - this.position.x) * 180) / Math.PI;
    let diff = targetAngle - this.heading;

    // Normalize to -180 to 180
    while (diff > 180) diff -= 360;
    while (diff < -180) diff += 360;

    // Gradual turn
    if (Math.abs(diff) <= turnRate) {
      this.heading = targetAngle;
    } else {
      this.heading += Math.sign(diff) * turnRate;
    }

    // Normalize
    this.heading = ((this.heading % 360) + 360) % 360;
  }

  updateStuckState(): void {
    const dist = distance(this.position, this.lastPosition);

    if (dist < 0.1) {
      this.ticksWithoutMovement++;
      if (this.ticksWithoutMovement >= 3) {
        this.isStuck = true;
      }
    } else {
      this.ticksWithoutMovement = 0;
      this.isStuck = false;
      this.escapeHeading = null;
    }

    this.lastPosition = { ...this.position };
  }

  getEscapeDirection(currentHeading: number): number {
    // Generate escape direction - opposite + random offset
    const offset = (Math.random() - 0.5) * 120;
    return (currentHeading + 180 + offset + 360) % 360;
  }

  updateWanderlust(worldWidth: number, worldHeight: number): void {
    this.ticksSinceDiscovery++;

    // Increase wanderlust over time without discoveries
    if (this.ticksSinceDiscovery > 20) {
      this.wanderlust = Math.min(1.0, this.wanderlust + 0.02);
    }

    // Decay wanderlust when near edges (exploring)
    const edgeMargin = 3;
    if (
      this.position.x < edgeMargin ||
      this.position.x > worldWidth - edgeMargin ||
      this.position.y < edgeMargin ||
      this.position.y > worldHeight - edgeMargin
    ) {
      this.wanderlust = Math.max(0, this.wanderlust - 0.05);
    }
  }

  resetDiscoveryTimer(): void {
    this.ticksSinceDiscovery = 0;
    this.wanderlust = Math.max(0, this.wanderlust - 0.3);
  }
}
