/**
 * Main entry point for the browser-based robot simulation.
 *
 * This demo showcases TesseraiDB's declarative PDDL-based robot control:
 *
 * **Architecture:**
 * - PDDL predicates describe world state (at, adjacent, obstacle, etc.)
 * - Action preconditions checked directly via reactive rules
 * - No planning search per tick - O(1) action selection
 * - PDDL domain still defines the semantics (shared across languages)
 *
 * **Why reactive instead of planning?**
 * - Real-time robotics needs "best action NOW" not "sequence to goal"
 * - Planning is expensive (O(exponential)) - unsuitable for per-tick
 * - Reactive rules give same behavior, much faster
 * - PDDL planner still useful for validation & rare high-level planning
 */

import { SimulationWorld } from "./simulation-world";
import { Renderer } from "./renderer";
import { initWasmEngine } from "./ontology-store";
import { PlanningController } from "./planning-controller";

// Configuration
let config = {
  width: 40,
  height: 25,
  robots: 5,
  objects: 15,
  obstacles: 20,
  batteryCapacity: 100,
};

// State
let world: SimulationWorld | null = null;
let renderer: Renderer | null = null;
let isRunning = false;
let animationId: number | null = null;
let tickCount = 0;

// Planning controller - kept for domain validation (not used for per-tick decisions)
let planningController: PlanningController | null = null;

// NOTE: No hardcoded SWRL_RULES, TBOX_CLASSES, or TBOX_PROPERTIES!
// Everything is now queried dynamically from the ontology via SPARQL.
// This is the key to language-agnostic, ontology-driven architecture.

// PDDL Domain Definition with Multi-Robot Coordination
// This domain handles collision avoidance declaratively via robot-blocking predicates
const PDDL_DOMAIN = `(define (domain robot-exploration-coordination)
  (:requirements :strips :typing :negative-preconditions)

  (:types
    robot
    location
    object
  )

  (:predicates
    ;; Position predicates
    (at ?r - robot ?l - location)
    (adjacent ?l1 - location ?l2 - location)

    ;; Blocking predicates - obstacles and other robots
    (obstacle ?l - location)
    (robot-blocking ?l - location)         ; Cell occupied by another robot

    ;; Home/base predicates - now per-robot
    (base ?l - location)                   ; Global base location
    (home-position ?r - robot ?l - location)  ; Per-robot home (offset from base)

    ;; Object predicates
    (object-at ?o - object ?l - location)
    (collected ?o - object)
    (carrying ?r - robot ?o - object)

    ;; Robot state predicates
    (low-battery ?r - robot)
    (at-base ?r - robot)
    (explored ?r - robot ?l - location)
  )

  ;; Move action - respects both obstacles AND other robots
  (:action move
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (robot-blocking ?to))           ; Cannot move into cell with another robot
      (not (low-battery ?r))
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (explored ?r ?to)
      (not (at-base ?r))
      (robot-blocking ?to)                 ; Mark new position as blocked
      (not (robot-blocking ?from))         ; Clear old position
    )
  )

  ;; Collect action
  (:action collect
    :parameters (?r - robot ?l - location ?o - object)
    :precondition (and
      (at ?r ?l)
      (object-at ?o ?l)
      (not (collected ?o))
      (not (low-battery ?r))
    )
    :effect (and
      (collected ?o)
      (carrying ?r ?o)
      (not (object-at ?o ?l))
    )
  )

  ;; Return to robot's assigned home position
  (:action return-to-home
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (robot-blocking ?to))
      (low-battery ?r)
      (home-position ?r ?to)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (robot-blocking ?to)
      (not (robot-blocking ?from))
      (at-base ?r)
    )
  )

  ;; Move toward home when not adjacent
  (:action move-toward-home
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (robot-blocking ?to))
      (low-battery ?r)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (robot-blocking ?to)
      (not (robot-blocking ?from))
    )
  )

  ;; Recharge at any base location
  (:action recharge
    :parameters (?r - robot ?l - location)
    :precondition (and
      (at ?r ?l)
      (base ?l)
      (low-battery ?r)
    )
    :effect (and
      (not (low-battery ?r))
      (at-base ?r)
    )
  )

  ;; Wait action - when path is blocked by another robot
  (:action wait
    :parameters (?r - robot ?l - location)
    :precondition (at ?r ?l)
    :effect ()
  )
)`;

/**
 * Initialize the simulation.
 */
function initSimulation(): void {
  world = new SimulationWorld(config.width, config.height);
  world.initialize(config.robots, config.objects, config.obstacles, config.batteryCapacity);

  // Always set planning controller (this demo showcases declarative planning)
  if (planningController) {
    world.setPlanningController(planningController);
  }

  const canvas = document.getElementById("canvas") as HTMLCanvasElement;
  renderer = new Renderer(canvas);
  renderer.reset();

  tickCount = 0;
  updateStats();
  updateRobotList();
  render();

  updateStatus("paused");
}

/**
 * Main simulation loop.
 * Uses reactive rule evaluation for robot decisions (O(1) per tick).
 */
async function simulationLoop(): Promise<void> {
  if (!isRunning || !world) return;

  // Execute reactive actions for all robots (synchronous, no planning)
  for (const robot of world.robots.filter((r) => r.isActive)) {
    world.executeReactiveAction(robot.id);
  }

  world.tick();
  tickCount = world.currentTick;

  render();
  updateStats();
  updateRobotList();

  // Check win condition
  if (world.isComplete()) {
    isRunning = false;
    updateStatus("ended", "All objects collected!");
    return;
  }

  // Continue loop - faster tick rate since no planning delay
  animationId = requestAnimationFrame(() => {
    setTimeout(simulationLoop, 100); // ~10 FPS (was 7 with planning)
  });
}

/**
 * Update the control mode stats display.
 */
function updateControlStats(): void {
  // With reactive control, planning stats are not applicable
  document.getElementById("planningTime")!.textContent = "N/A";
  document.getElementById("planningStates")!.textContent = "N/A";
  document.getElementById("planningLength")!.textContent = "N/A";
}

function render(): void {
  if (renderer && world) {
    renderer.render(world);
  }
}

function updateStats(): void {
  if (!world) return;

  const stats = world.getStats();
  document.getElementById("tick")!.textContent = tickCount.toString();
  document.getElementById("objects")!.textContent = `${stats.collectedObjects} / ${stats.totalObjects}`;
  document.getElementById("collisions")!.textContent = stats.totalCollisions.toString();
}

function updateRobotList(): void {
  if (!world) return;

  const robotListEl = document.getElementById("robotList")!;
  robotListEl.innerHTML = world.robots
    .map((r) => {
      const known = world!.knownWorlds.get(r.id);
      const isEscaping = r.currentAction.includes("ESCAPE");
      const isInLoop = known?.loopDetected || false;
      const indicator = isEscaping ? " 🚀" : isInLoop ? " 🔄" : "";
      const areaStr = known && known.coverageArea > 0 ? known.coverageArea.toFixed(1) : "-";

      return `
        <div class="robot-item">
          <div class="robot-dot" style="background: ${r.color}"></div>
          <div class="robot-info">
            <div>${r.id.replace("robot", "Robot ")}${indicator}</div>
            <div class="robot-stats">${r.objectsCollected} obj | ${r.collisionCount} col | area: ${areaStr}</div>
            <div class="robot-action" title="${r.currentAction}">${r.currentAction}</div>
          </div>
        </div>
      `;
    })
    .join("");
}

function updateStatus(status: "running" | "paused" | "ended", text?: string): void {
  const el = document.getElementById("status")!;
  el.className = "status status-" + status;
  el.textContent = text || (status === "running" ? "Running (Reactive)" : status === "paused" ? "Paused" : "Ended");
}

function updateConfigInputs(): void {
  (document.getElementById("cfgWidth") as HTMLInputElement).value = config.width.toString();
  (document.getElementById("cfgHeight") as HTMLInputElement).value = config.height.toString();
  (document.getElementById("cfgRobots") as HTMLInputElement).value = config.robots.toString();
  (document.getElementById("cfgObjects") as HTMLInputElement).value = config.objects.toString();
  (document.getElementById("cfgObstacles") as HTMLInputElement).value = config.obstacles.toString();
  (document.getElementById("cfgBattery") as HTMLInputElement).value = config.batteryCapacity.toString();
}

function renderOntologyTab(): void {
  if (!world) return;

  // Get twins from ontology (dynamic query)
  const twins = world.ontology.getAllTwins();
  document.getElementById("twinCount")!.textContent = `(${twins.length})`;

  const twinsTable = document.getElementById("twinsTable")!;
  twinsTable.innerHTML = twins
    .map(
      (t) => `
      <tr>
        <td><span style="color: ${t.type === "Robot" ? "#3498db" : t.type === "Object" ? "#f1c40f" : "#888"}">${t.type}</span></td>
        <td style="font-family: monospace; font-size: 0.65rem;">${t.id}</td>
        <td style="font-size: 0.6rem; color: #888;">${t.properties}</td>
      </tr>
    `
    )
    .join("");

  // Render rules from ontology (dynamic query)
  const rules = world.ontology.getAllRules();
  document.getElementById("ruleCount")!.textContent = `(${rules.length})`;
  document.getElementById("rulesContent")!.innerHTML = rules.map(
    (r) => `
      <div class="rule-card">
        <div class="rule-id">${r.id}</div>
        <div class="rule-name">${r.name}</div>
        <div class="rule-condition">${r.condition} → ${r.conclusion}</div>
      </div>
    `
  ).join("");

  // Render TBox classes from ontology (dynamic query)
  const classes = world.ontology.getAllClasses();
  document.getElementById("classesContent")!.innerHTML = classes.map(
    (c) => `<div class="axiom-item"><span class="axiom-class">${c}</span></div>`
  ).join("");

  // Render TBox properties from ontology (dynamic query)
  const properties = world.ontology.getAllProperties();
  document.getElementById("propertiesContent")!.innerHTML = properties.map(
    (p) => `<div class="axiom-item"><span class="axiom-prop">${p.name}</span> <span class="axiom-type">(${p.type})</span></div>`
  ).join("");

  // Render Behavior Configuration from ontology (dynamic query - no hardcoding!)
  const configs = world.ontology.getAllConfigurations();
  const configColors: Record<string, string> = {
    "ExplorationConfig": "#3498db",
    "EscapeConfig": "#e74c3c",
    "DetectionConfig": "#9b59b6",
    "ActionConfig": "#2ecc71",
  };

  const configHtml = configs.map(cfg => {
    const color = configColors[cfg.configType] || "#888";
    const propsHtml = cfg.properties
      .map(p => `<div>${p.name}: <span style="color: #f1c40f;">${p.value}</span></div>`)
      .join("");
    return `
      <div style="background: #1a1a2e; padding: 6px; border-radius: 4px;">
        <div style="color: ${color}; font-weight: bold; margin-bottom: 4px;">${cfg.configType.replace("Config", "")}</div>
        ${propsHtml}
      </div>
    `;
  }).join("");

  document.getElementById("configContent")!.innerHTML = configHtml || "<div style='color: #888;'>No configuration found in ontology</div>";
}

// Event handlers
function setupEventHandlers(): void {
  document.getElementById("startBtn")!.onclick = () => {
    if (!isRunning) {
      isRunning = true;
      updateStatus("running");
      simulationLoop();
    }
  };

  document.getElementById("pauseBtn")!.onclick = () => {
    isRunning = false;
    if (animationId) {
      cancelAnimationFrame(animationId);
    }
    updateStatus("paused");
  };

  document.getElementById("resetBtn")!.onclick = () => {
    isRunning = false;
    if (animationId) {
      cancelAnimationFrame(animationId);
    }
    renderer?.reset();
    initSimulation();
  };

  document.getElementById("applyBtn")!.onclick = () => {
    isRunning = false;
    if (animationId) {
      cancelAnimationFrame(animationId);
    }

    // Parse and clamp values to safe limits
    const clamp = (val: number, min: number, max: number) => Math.max(min, Math.min(max, val));

    config = {
      width: clamp(parseInt((document.getElementById("cfgWidth") as HTMLInputElement).value) || 40, 10, 200),
      height: clamp(parseInt((document.getElementById("cfgHeight") as HTMLInputElement).value) || 25, 10, 150),
      robots: clamp(parseInt((document.getElementById("cfgRobots") as HTMLInputElement).value) || 5, 1, 20),
      objects: clamp(parseInt((document.getElementById("cfgObjects") as HTMLInputElement).value) || 15, 1, 100),
      obstacles: clamp(parseInt((document.getElementById("cfgObstacles") as HTMLInputElement).value) || 20, 0, 100),
      batteryCapacity: clamp(parseInt((document.getElementById("cfgBattery") as HTMLInputElement)?.value) || 100, 10, 1000),
    };

    // Update inputs to show clamped values
    (document.getElementById("cfgWidth") as HTMLInputElement).value = config.width.toString();
    (document.getElementById("cfgHeight") as HTMLInputElement).value = config.height.toString();
    (document.getElementById("cfgRobots") as HTMLInputElement).value = config.robots.toString();
    (document.getElementById("cfgObjects") as HTMLInputElement).value = config.objects.toString();
    (document.getElementById("cfgObstacles") as HTMLInputElement).value = config.obstacles.toString();
    (document.getElementById("cfgBattery") as HTMLInputElement).value = config.batteryCapacity.toString();

    renderer?.reset();
    initSimulation();
  };

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    (btn as HTMLElement).onclick = () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const tabId = (btn as HTMLElement).dataset.tab;
      document.getElementById("tab-" + tabId)!.classList.add("active");

      if (tabId === "ontology") {
        renderOntologyTab();
      }
      if (tabId === "pddl") {
        renderPddlTab();
      }
    };
  });

  document.getElementById("refreshOntology")!.onclick = renderOntologyTab;

  // Planning API URL change - reconnect
  const planningApiUrl = document.getElementById("planningApiUrl") as HTMLInputElement;
  planningApiUrl.onchange = () => {
    // Reconnect with new URL
    initPlanningController(planningApiUrl.value);
  };
}

/**
 * Initialize the planning controller for domain validation.
 * Note: Per-tick decisions use reactive control, not planning.
 */
async function initPlanningController(apiUrl: string): Promise<void> {
  const statusEl = document.getElementById("planningStatus")!;

  statusEl.textContent = "Reactive Mode";
  statusEl.className = "stat-value connected";

  // Try to connect for domain validation (optional)
  try {
    planningController = new PlanningController(apiUrl);
    const initialized = await planningController.initialize();
    if (initialized) {
      console.log("[Planning] API connected for domain validation:", apiUrl);
    }
  } catch (e) {
    console.log("[Planning] API not available (reactive mode doesn't need it)");
  }

  // Update stats to show reactive mode
  updateControlStats();
}

/**
 * Render the PDDL tab with syntax highlighting.
 */
function renderPddlTab(): void {
  // Extract types
  const typesMatch = PDDL_DOMAIN.match(/\(:types([\s\S]*?)\)/);
  const typesContent = typesMatch ? typesMatch[1].trim() : "";
  document.getElementById("pddlTypes")!.innerHTML = highlightPddl(typesContent);

  // Extract predicates
  const predicatesMatch = PDDL_DOMAIN.match(/\(:predicates([\s\S]*?)\)\s*\(:action/);
  const predicatesContent = predicatesMatch ? predicatesMatch[1].trim() : "";
  document.getElementById("pddlPredicates")!.innerHTML = highlightPddl(predicatesContent);

  // Extract and render actions
  const actionMatches = PDDL_DOMAIN.matchAll(/\(:action\s+(\w+)([\s\S]*?)(?=\(:action|\)\s*$)/g);
  const actionsHtml = Array.from(actionMatches).map(match => {
    const actionName = match[1];
    const actionBody = match[2].trim();
    return `
      <div class="pddl-code" style="margin-bottom: 8px;">
        <span class="action">(:action ${actionName}</span>
${highlightPddl(actionBody)}
      </div>
    `;
  }).join("");
  document.getElementById("pddlActions")!.innerHTML = actionsHtml;

  // Render full domain
  document.getElementById("pddlFullDomain")!.innerHTML = highlightPddl(PDDL_DOMAIN);

  // Update info
  document.getElementById("pddlDomainName")!.textContent = "robot-exploration-coordination";
  document.getElementById("pddlRequirements")!.textContent = ":strips :typing :negative-preconditions";
  document.getElementById("pddlActionCount")!.textContent = "7";
}

/**
 * Simple PDDL syntax highlighting.
 */
function highlightPddl(code: string): string {
  return code
    // Comments
    .replace(/(;;.*)/g, '<span class="comment">$1</span>')
    // Keywords
    .replace(/(:requirements|:types|:predicates|:action|:parameters|:precondition|:effect)/g, '<span class="keyword">$1</span>')
    // Types after hyphen
    .replace(/- (robot|location|object)/g, '- <span class="type">$1</span>')
    // Predicates in parentheses (including new robot-blocking and home-position)
    .replace(/\((at|adjacent|obstacle|base|object-at|collected|carrying|low-battery|at-base|explored|robot-blocking|home-position)\s/g, '(<span class="predicate">$1</span> ')
    // Boolean operators
    .replace(/\((and|not|or)\s/g, '(<span class="keyword">$1</span> ');
}

// Initialize on load
window.addEventListener("DOMContentLoaded", async () => {
  console.log("Initializing TesseraiDB Robot Simulation...");
  console.log("This demo showcases declarative PDDL planning for robot control.");
  updateStatus("paused", "Loading...");

  try {
    // Initialize TesseraiDB WASM engine for ontology reasoning
    await initWasmEngine();

    updateConfigInputs();
    setupEventHandlers();

    // Auto-connect to Planning API
    const planningApiUrl = (document.getElementById("planningApiUrl") as HTMLInputElement).value;
    await initPlanningController(planningApiUrl);

    initSimulation();
    console.log("Simulation ready. Click Start to begin.");
  } catch (error) {
    console.error("Failed to initialize:", error);
    updateStatus("ended", "Failed to load");
  }
});
