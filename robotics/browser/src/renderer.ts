/**
 * Canvas renderer for the robot simulation.
 */

import { SimulationWorld } from "./simulation-world";

// Maximum canvas dimension to avoid browser limits
const MAX_CANVAS_SIZE = 4096;
const DEFAULT_CELL_SIZE = 28;

export class Renderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private revealedCells: Set<string> = new Set();
  private cellSize: number = DEFAULT_CELL_SIZE;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d")!;
  }

  /**
   * Calculate optimal cell size to fit world within canvas limits.
   */
  private calculateCellSize(worldWidth: number, worldHeight: number): number {
    const maxDimension = Math.max(worldWidth, worldHeight);
    const idealSize = DEFAULT_CELL_SIZE;

    // If canvas would exceed limits, shrink cell size
    if (maxDimension * idealSize > MAX_CANVAS_SIZE) {
      return Math.floor(MAX_CANVAS_SIZE / maxDimension);
    }

    return idealSize;
  }

  render(world: SimulationWorld): void {
    // Calculate dynamic cell size
    this.cellSize = this.calculateCellSize(world.width, world.height);
    const CELL_SIZE = this.cellSize;

    const width = world.width * CELL_SIZE;
    const height = world.height * CELL_SIZE;

    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }

    const ctx = this.ctx;

    // Background
    ctx.fillStyle = "#16213e";
    ctx.fillRect(0, 0, width, height);

    // Grid
    ctx.strokeStyle = "#252545";
    ctx.lineWidth = 1;
    for (let x = 0; x <= world.width; x++) {
      ctx.beginPath();
      ctx.moveTo(x * CELL_SIZE, 0);
      ctx.lineTo(x * CELL_SIZE, height);
      ctx.stroke();
    }
    for (let y = 0; y <= world.height; y++) {
      ctx.beginPath();
      ctx.moveTo(0, y * CELL_SIZE);
      ctx.lineTo(width, y * CELL_SIZE);
      ctx.stroke();
    }

    // Pheromones
    for (const p of world.pheromones) {
      const robot = world.robots.find((r) => r.id === p.depositedBy);
      const color = robot?.color || "#888";

      const size = 1.5 + p.strength;
      ctx.globalAlpha = 0.2 + p.strength * 0.3;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(p.position.x * CELL_SIZE, p.position.y * CELL_SIZE, size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Obstacles (stone-like)
    for (const obs of world.obstacles) {
      const ox = obs.position.x * CELL_SIZE;
      const oy = obs.position.y * CELL_SIZE;
      const r = obs.radius * CELL_SIZE;

      ctx.fillStyle = "#555";
      ctx.beginPath();

      // Irregular polygon
      const points = 8;
      for (let i = 0; i < points; i++) {
        const angle = (i / points) * Math.PI * 2;
        const variation = 0.8 + Math.sin(angle * 3 + parseFloat(obs.id.replace(/\D/g, ""))) * 0.2;
        const px = ox + Math.cos(angle) * r * variation;
        const py = oy + Math.sin(angle) * r * variation;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();

      // Inner shadow
      ctx.fillStyle = "#444";
      ctx.beginPath();
      for (let i = 0; i < points; i++) {
        const angle = (i / points) * Math.PI * 2;
        const variation = 0.6 + Math.sin(angle * 3 + parseFloat(obs.id.replace(/\D/g, ""))) * 0.15;
        const px = ox + Math.cos(angle) * r * variation;
        const py = oy + Math.sin(angle) * r * variation;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();
    }

    // Objects
    for (const obj of world.objects) {
      if (obj.collected) continue;

      const ox = obj.position.x * CELL_SIZE;
      const oy = obj.position.y * CELL_SIZE;

      // Glow
      ctx.shadowColor = "#f1c40f";
      ctx.shadowBlur = 10;
      ctx.fillStyle = "#f1c40f";
      ctx.beginPath();
      ctx.arc(ox, oy, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Core
      ctx.fillStyle = "#f39c12";
      ctx.beginPath();
      ctx.arc(ox, oy, 5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Robots
    for (const robot of world.robots) {
      const rx = robot.position.x * CELL_SIZE;
      const ry = robot.position.y * CELL_SIZE;
      const rad = (robot.heading * Math.PI) / 180;

      // Sensor range
      ctx.fillStyle = robot.color + "22";
      ctx.strokeStyle = robot.color + "66";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(rx, ry, robot.sensorRange * CELL_SIZE, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Robot body (arrow shape)
      ctx.save();
      ctx.translate(rx, ry);
      ctx.rotate(rad);

      ctx.fillStyle = robot.color;
      ctx.beginPath();
      ctx.moveTo(12, 0);
      ctx.lineTo(-8, -7);
      ctx.lineTo(-4, 0);
      ctx.lineTo(-8, 7);
      ctx.closePath();
      ctx.fill();

      // Outline
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.restore();

      // Update revealed cells
      const range = robot.sensorRange;
      for (let dx = -Math.ceil(range); dx <= Math.ceil(range); dx++) {
        for (let dy = -Math.ceil(range); dy <= Math.ceil(range); dy++) {
          const cx = Math.floor(robot.position.x + dx);
          const cy = Math.floor(robot.position.y + dy);
          if (cx >= 0 && cx < world.width && cy >= 0 && cy < world.height) {
            if (Math.sqrt(dx * dx + dy * dy) <= range) {
              this.revealedCells.add(`${cx},${cy}`);
            }
          }
        }
      }
    }

    // Fog of war
    ctx.fillStyle = "#0a0a15";
    for (let gx = 0; gx < world.width; gx++) {
      for (let gy = 0; gy < world.height; gy++) {
        if (!this.revealedCells.has(`${gx},${gy}`)) {
          ctx.fillRect(gx * CELL_SIZE, gy * CELL_SIZE, CELL_SIZE, CELL_SIZE);
        }
      }
    }
  }

  reset(): void {
    this.revealedCells.clear();
  }
}
