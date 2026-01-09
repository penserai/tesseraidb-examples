/**
 * KnownWorld class - tracks what each robot has discovered.
 * Implements partial observability and geometric stuck detection.
 */

import { Position, WorldObject, Obstacle, distance } from "./types";

export class KnownWorld {
  robotId: string;

  // Discovered entities
  discoveredObjects: Map<string, WorldObject> = new Map();
  discoveredObstacles: Map<string, Obstacle> = new Map();

  // Exploration history
  exploredPositions: Set<string> = new Set();
  recentPositions: Array<[number, number]> = [];
  readonly maxRecentPositions = 30;

  // Loop detection
  loopDetected: boolean = false;
  stuckCounter: number = 0;

  // Geometric metrics
  coverageArea: number = 0;
  pathKnottiness: number = 0;

  // Escape mode state
  escapeMode: boolean = false;
  escapeTarget: Position | null = null;
  escapeTicksRemaining: number = 0;
  clutterCentroid: Position | null = null;

  // World bounds discovery
  knownMinX: number | null = null;
  knownMaxX: number | null = null;
  knownMinY: number | null = null;
  knownMaxY: number | null = null;

  constructor(robotId: string) {
    this.robotId = robotId;
  }

  hasDiscoveredObject(objId: string): boolean {
    return this.discoveredObjects.has(objId);
  }

  hasDiscoveredObstacle(obsId: string): boolean {
    return this.discoveredObstacles.has(obsId);
  }

  discoverObject(obj: WorldObject): void {
    if (!this.discoveredObjects.has(obj.id)) {
      this.discoveredObjects.set(obj.id, { ...obj });
    }
  }

  discoverObstacle(obs: Obstacle): void {
    if (!this.discoveredObstacles.has(obs.id)) {
      this.discoveredObstacles.set(obs.id, { ...obs });
    }
  }

  getUncollectedKnownObjects(): WorldObject[] {
    return Array.from(this.discoveredObjects.values()).filter((o) => !o.collected);
  }

  getNearestKnownObject(fromPos: Position): WorldObject | null {
    const uncollected = this.getUncollectedKnownObjects();
    if (uncollected.length === 0) return null;

    return uncollected.reduce((nearest, obj) =>
      distance(fromPos, obj.position) < distance(fromPos, nearest.position) ? obj : nearest
    );
  }

  getSecondNearestObject(fromPos: Position, exclude: WorldObject): WorldObject | null {
    const uncollected = this.getUncollectedKnownObjects().filter((o) => o.id !== exclude.id);
    if (uncollected.length === 0) return null;

    return uncollected.reduce((nearest, obj) =>
      distance(fromPos, obj.position) < distance(fromPos, nearest.position) ? obj : nearest
    );
  }

  recordExploration(pos: Position): void {
    const cellX = Math.floor(pos.x);
    const cellY = Math.floor(pos.y);
    const key = `${cellX},${cellY}`;

    this.exploredPositions.add(key);

    // Update recent positions buffer
    this.recentPositions.push([cellX, cellY]);
    if (this.recentPositions.length > this.maxRecentPositions) {
      this.recentPositions.shift();
    }

    // Update world bounds knowledge
    if (this.knownMinX === null || cellX < this.knownMinX) this.knownMinX = cellX;
    if (this.knownMaxX === null || cellX > this.knownMaxX) this.knownMaxX = cellX;
    if (this.knownMinY === null || cellY < this.knownMinY) this.knownMinY = cellY;
    if (this.knownMaxY === null || cellY > this.knownMaxY) this.knownMaxY = cellY;

    // Check for loop
    this.checkForLoop();
  }

  private checkForLoop(): void {
    if (this.recentPositions.length < 10) {
      this.loopDetected = false;
      this.coverageArea = 0;
      this.pathKnottiness = 0;
      return;
    }

    // Calculate coverage area (convex hull)
    const positions = this.recentPositions.slice(-20);
    this.coverageArea = this.calculateConvexHullArea(positions);

    // Calculate path knottiness (total angular change)
    this.pathKnottiness = this.calculatePathKnottiness(positions);

    // Count cell visits
    const cellCounts = new Map<string, number>();
    for (const [x, y] of this.recentPositions) {
      const key = `${x},${y}`;
      cellCounts.set(key, (cellCounts.get(key) || 0) + 1);
    }
    const maxVisits = Math.max(...cellCounts.values());
    const uniqueCells = cellCounts.size;

    // Detection criteria - multiple ways to detect circling/stuck behavior
    const smallArea = this.coverageArea < 15;
    const highKnottiness = this.pathKnottiness > Math.PI * 3; // ~540 degrees of turning
    const veryHighKnottiness = this.pathKnottiness > Math.PI * 6; // ~1080 degrees - definitely circling
    const repeatedVisits = maxVisits >= 3;
    const lowUniqueCells = uniqueCells < this.recentPositions.length * 0.4; // Less than 40% unique

    // Circular orbit detection: lots of turning even with larger area
    const circularOrbit = veryHighKnottiness && this.recentPositions.length >= 15;

    if (repeatedVisits || circularOrbit || lowUniqueCells) {
      this.loopDetected = true;
      this.stuckCounter++;
    } else if (smallArea && highKnottiness) {
      this.loopDetected = true;
      this.stuckCounter++;
    } else if (smallArea && this.recentPositions.length >= 15) {
      this.loopDetected = true;
      this.stuckCounter++;
    } else {
      this.loopDetected = false;
      this.stuckCounter = Math.max(0, this.stuckCounter - 1);
    }
  }

  private calculateConvexHullArea(points: Array<[number, number]>): number {
    if (points.length < 3) return 0;

    // Remove duplicates
    const unique = Array.from(new Set(points.map((p) => `${p[0]},${p[1]}`))).map((s) => {
      const [x, y] = s.split(",").map(Number);
      return [x, y] as [number, number];
    });

    if (unique.length < 3) return 0;

    // Graham scan for convex hull
    const sorted = [...unique].sort((a, b) => (a[0] === b[0] ? a[1] - b[1] : a[0] - b[0]));

    const cross = (o: [number, number], a: [number, number], b: [number, number]) =>
      (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);

    const lower: Array<[number, number]> = [];
    for (const p of sorted) {
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
        lower.pop();
      }
      lower.push(p);
    }

    const upper: Array<[number, number]> = [];
    for (const p of sorted.reverse()) {
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
        upper.pop();
      }
      upper.push(p);
    }

    lower.pop();
    upper.pop();
    const hull = [...lower, ...upper];

    if (hull.length < 3) return 0;

    // Shoelace formula for area
    let area = 0;
    for (let i = 0; i < hull.length; i++) {
      const j = (i + 1) % hull.length;
      area += hull[i][0] * hull[j][1];
      area -= hull[j][0] * hull[i][1];
    }

    return Math.abs(area) / 2;
  }

  private calculatePathKnottiness(positions: Array<[number, number]>): number {
    if (positions.length < 3) return 0;

    let totalAngle = 0;

    for (let i = 1; i < positions.length - 1; i++) {
      const [x0, y0] = positions[i - 1];
      const [x1, y1] = positions[i];
      const [x2, y2] = positions[i + 1];

      const v1x = x1 - x0;
      const v1y = y1 - y0;
      const v2x = x2 - x1;
      const v2y = y2 - y1;

      const len1 = Math.sqrt(v1x * v1x + v1y * v1y);
      const len2 = Math.sqrt(v2x * v2x + v2y * v2y);

      if (len1 > 0.01 && len2 > 0.01) {
        const dot = v1x * v2x + v1y * v2y;
        const cosAngle = Math.max(-1, Math.min(1, dot / (len1 * len2)));
        totalAngle += Math.acos(cosAngle);
      }
    }

    return totalAngle;
  }

  getLeastVisitedDirection(fromPos: Position, directions: number[]): number {
    let bestDirection = directions[0] || 0;
    let bestScore = Infinity;

    for (const angle of directions) {
      const rad = (angle * Math.PI) / 180;
      let visitCount = 0;

      for (const dist of [2, 4, 6, 8]) {
        const checkX = Math.round(fromPos.x + Math.cos(rad) * dist);
        const checkY = Math.round(fromPos.y + Math.sin(rad) * dist);
        const key = `${checkX},${checkY}`;

        if (this.exploredPositions.has(key)) {
          visitCount++;
        }
      }

      if (visitCount < bestScore) {
        bestScore = visitCount;
        bestDirection = angle;
      }
    }

    return bestDirection;
  }

  clearEscapeMode(): void {
    this.escapeMode = false;
    this.escapeTarget = null;
    this.escapeTicksRemaining = 0;
    this.clutterCentroid = null;
    this.recentPositions = [];
    this.coverageArea = 0;
    this.pathKnottiness = 0;
  }
}
