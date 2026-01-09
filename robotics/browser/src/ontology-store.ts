/**
 * OntologyStore - In-browser SPARQL store using TesseraiDB WASM.
 * Provides the same functionality as the backend TesseraiDB service.
 *
 * KEY PRINCIPLE: All behavior parameters are stored in the ontology,
 * making the application code a thin query-and-execute client.
 * This enables language-agnostic implementations.
 */

import init, { Store, Term } from "oxigraph/web";
import { Robot } from "./robot";
import { WorldObject, Obstacle, RobotState } from "./types";
import { KnownWorld } from "./known-world";
import { ROBOTICS_ONTOLOGY_TURTLE, BehaviorParameters, LOAD_PARAMETERS_QUERY } from "./ontology-schema";

// Aligned with shared ontology at examples/ontologies/robot_simulation.ttl
const ROBO = "http://tesserai.io/ontology/robot_simulation#";

let wasmInitialized = false;

/**
 * Initialize the TesseraiDB WASM module. Must be called before using OntologyStore.
 */
export async function initWasmEngine(): Promise<void> {
  if (!wasmInitialized) {
    await init();
    wasmInitialized = true;
    console.log("TesseraiDB WASM engine initialized");
  }
}

export class OntologyStore {
  private store: Store;
  private _params: BehaviorParameters | null = null;

  constructor() {
    if (!wasmInitialized) {
      throw new Error("TesseraiDB WASM not initialized. Call initWasmEngine() first.");
    }
    this.store = new Store();
  }

  /**
   * Get behavior parameters from ontology (cached after first load).
   */
  get params(): BehaviorParameters {
    if (!this._params) {
      this._params = this.loadParameters();
    }
    return this._params;
  }

  /**
   * Initialize the ontology with full TBox schema and default configurations.
   * All behavior parameters are loaded from the ontology, not hardcoded.
   */
  initializeOntology(): void {
    // Load the complete ontology schema with all parameters
    this.store.load(ROBOTICS_ONTOLOGY_TURTLE, { format: "text/turtle" });
    console.log("Ontology schema loaded with behavior parameters");

    // Pre-load parameters
    this._params = this.loadParameters();
    console.log("Behavior parameters loaded from ontology:", this._params);
  }

  /**
   * Load all behavior parameters from the ontology via SPARQL.
   * This is the key to language-agnostic implementations.
   */
  private loadParameters(): BehaviorParameters {
    const results = this.store.query(LOAD_PARAMETERS_QUERY) as Map<string, Term>[];

    if (results.length === 0) {
      console.warn("No behavior parameters found in ontology, using defaults");
      return this.getDefaultParameters();
    }

    const r = results[0];
    const getFloat = (key: string, def: number) => parseFloat(r.get(key)?.value || String(def));
    const getInt = (key: string, def: number) => parseInt(r.get(key)?.value || String(def));

    return {
      exploration: {
        quadrantCrossingBonus: getFloat("quadrantCrossingBonus", 40),
        sameQuadrantPenalty: getFloat("sameQuadrantPenalty", 20),
        centerApproachBonus: getFloat("centerApproachBonus", 30),
        edgeDistanceThreshold: getFloat("edgeDistanceThreshold", 0.3),
        unexploredTargetBonus: getFloat("unexploredTargetBonus", 25),
        unexploredPathBonus: getFloat("unexploredPathBonus", 10),
        distanceBonusMultiplier: getFloat("distanceBonusMultiplier", 0.5),
        directionSampleCount: getInt("directionSampleCount", 24),
        ventureDistanceFactor: getFloat("ventureDistanceFactor", 2.5),
        gridMarginFactor: getFloat("gridMarginFactor", 0.1),
      },
      escape: {
        angleVariance: getFloat("escapeAngleVariance", 90),
        baseAngleOffset: getFloat("escapeBaseAngleOffset", 180),
        tickDuration: getInt("escapeTickDuration", 25),
        minDistance: getFloat("escapeMinDistance", 12),
        distanceFactor: getFloat("escapeDistanceFactor", 3),
        targetReachedDistance: getFloat("escapeTargetReachedDistance", 2),
        clutterClearDistance: getFloat("escapeClutterClearDistance", 12),
      },
      detection: {
        lowBatteryThreshold: getFloat("lowBatteryThreshold", 20),
        batteryDrainRate: getFloat("batteryDrainRate", 0.05),
        atObjectDistance: getFloat("atObjectDistance", 1),
        nearObjectDistance: getFloat("nearObjectDistance", 3),
        mustAvoidDistance: getFloat("mustAvoidDistance", 1.5),
        emergencyAvoidDistance: getFloat("emergencyAvoidDistance", 0.8),
        smallCoverageThreshold: getFloat("smallCoverageThreshold", 15),
        severelyCoverageThreshold: getFloat("severelyCoverageThreshold", 8),
        highKnottinessThreshold: getFloat("highKnottinessThreshold", Math.PI * 3),
        veryHighKnottinessThreshold: getFloat("veryHighKnottinessThreshold", Math.PI * 6),
        minPositionsForDetection: getInt("minPositionsForDetection", 10),
        lowUniqueCellsRatio: getFloat("lowUniqueCellsRatio", 0.4),
        repeatedVisitThreshold: getInt("repeatedVisitThreshold", 3),
      },
      action: {
        defaultSpeed: getFloat("defaultSpeed", 1),
        turnRateExplore: getFloat("turnRateExplore", 25),
        turnRateDirect: getFloat("turnRateDirect", 90),
        avoidanceCheckDistance: getFloat("avoidanceCheckDistance", 2),
        collisionBuffer: getFloat("collisionBuffer", 0.3),
        obstacleBuffer: getFloat("obstacleBuffer", 0.5),
        avoidanceJitter: getFloat("avoidanceJitter", 20),
        turnAroundJitter: getFloat("turnAroundJitter", 90),
        worldBoundaryMargin: getFloat("worldBoundaryMargin", 3),
      },
    };
  }

  /**
   * Fallback defaults if ontology query fails.
   */
  private getDefaultParameters(): BehaviorParameters {
    return {
      exploration: {
        quadrantCrossingBonus: 40,
        sameQuadrantPenalty: 20,
        centerApproachBonus: 30,
        edgeDistanceThreshold: 0.3,
        unexploredTargetBonus: 25,
        unexploredPathBonus: 10,
        distanceBonusMultiplier: 0.5,
        directionSampleCount: 24,
        ventureDistanceFactor: 2.5,
        gridMarginFactor: 0.1,
      },
      escape: {
        angleVariance: 90,
        baseAngleOffset: 180,
        tickDuration: 25,
        minDistance: 12,
        distanceFactor: 3,
        targetReachedDistance: 2,
        clutterClearDistance: 12,
      },
      detection: {
        lowBatteryThreshold: 20,
        batteryDrainRate: 0.05,
        atObjectDistance: 1,
        nearObjectDistance: 3,
        mustAvoidDistance: 1.5,
        emergencyAvoidDistance: 0.8,
        smallCoverageThreshold: 15,
        severelyCoverageThreshold: 8,
        highKnottinessThreshold: Math.PI * 3,
        veryHighKnottinessThreshold: Math.PI * 6,
        minPositionsForDetection: 10,
        lowUniqueCellsRatio: 0.4,
        repeatedVisitThreshold: 3,
      },
      action: {
        defaultSpeed: 1,
        turnRateExplore: 25,
        turnRateDirect: 90,
        avoidanceCheckDistance: 2,
        collisionBuffer: 0.3,
        obstacleBuffer: 0.5,
        avoidanceJitter: 20,
        turnAroundJitter: 90,
        worldBoundaryMargin: 3,
      },
    };
  }

  /**
   * Initialize ABox with world entities (robots, objects, obstacles).
   */
  initializeWorld(robots: Robot[], objects: WorldObject[], obstacles: Obstacle[]): void {
    // Create a fresh store
    this.store = new Store();

    // Re-initialize TBox
    this.initializeOntology();

    // Add robots
    for (const robot of robots) {
      this.addRobot(robot);
    }

    // Add objects
    for (const obj of objects) {
      this.addObject(obj);
    }

    // Add obstacles
    for (const obs of obstacles) {
      this.addObstacle(obs);
    }
  }

  private addRobot(robot: Robot): void {
    const triples = `
      @prefix robo: <${ROBO}> .
      @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

      <urn:robot:${robot.id}> a robo:Robot ;
        robo:positionX "${robot.position.x}"^^xsd:float ;
        robo:positionY "${robot.position.y}"^^xsd:float ;
        robo:heading "${robot.heading}"^^xsd:float ;
        robo:batteryLevel "${robot.battery}"^^xsd:float ;
        robo:hasCollision "false"^^xsd:boolean ;
        robo:distanceToNearest "999"^^xsd:float ;
        robo:distanceToObstacle "999"^^xsd:float ;
        robo:coverageArea "0"^^xsd:float ;
        robo:pathKnottiness "0"^^xsd:float ;
        robo:recentPositionCount "0"^^xsd:integer ;
        robo:inLoop "false"^^xsd:boolean ;
        robo:stuckCounter "0"^^xsd:integer .
    `;

    this.store.load(triples, { format: "text/turtle" });
  }

  private addObject(obj: WorldObject): void {
    const triples = `
      @prefix robo: <${ROBO}> .
      @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

      <urn:object:${obj.id}> a robo:WorldObject ;
        robo:positionX "${obj.position.x}"^^xsd:float ;
        robo:positionY "${obj.position.y}"^^xsd:float ;
        robo:value "${obj.value}"^^xsd:float ;
        robo:collected "${obj.collected}"^^xsd:boolean .
    `;

    this.store.load(triples, { format: "text/turtle" });
  }

  private addObstacle(obs: Obstacle): void {
    const triples = `
      @prefix robo: <${ROBO}> .
      @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

      <urn:obstacle:${obs.id}> a robo:Obstacle ;
        robo:positionX "${obs.position.x}"^^xsd:float ;
        robo:positionY "${obs.position.y}"^^xsd:float ;
        robo:radius "${obs.radius}"^^xsd:float .
    `;

    this.store.load(triples, { format: "text/turtle" });
  }

  /**
   * Update robot state in the ontology.
   */
  updateRobotState(robot: Robot, known: KnownWorld, distToNearest: number, distToObstacle: number): void {
    const robotUri = `urn:robot:${robot.id}`;

    // Delete old values and insert new ones
    this.store.update(`
      PREFIX robo: <${ROBO}>
      PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

      DELETE {
        <${robotUri}> robo:positionX ?oldX .
        <${robotUri}> robo:positionY ?oldY .
        <${robotUri}> robo:heading ?oldH .
        <${robotUri}> robo:batteryLevel ?oldB .
        <${robotUri}> robo:hasCollision ?oldC .
        <${robotUri}> robo:distanceToNearest ?oldDN .
        <${robotUri}> robo:distanceToObstacle ?oldDO .
        <${robotUri}> robo:coverageArea ?oldCA .
        <${robotUri}> robo:pathKnottiness ?oldPK .
        <${robotUri}> robo:recentPositionCount ?oldRPC .
        <${robotUri}> robo:inLoop ?oldIL .
        <${robotUri}> robo:stuckCounter ?oldSC .
      }
      INSERT {
        <${robotUri}> robo:positionX "${robot.position.x}"^^xsd:float .
        <${robotUri}> robo:positionY "${robot.position.y}"^^xsd:float .
        <${robotUri}> robo:heading "${robot.heading}"^^xsd:float .
        <${robotUri}> robo:batteryLevel "${robot.battery}"^^xsd:float .
        <${robotUri}> robo:hasCollision "${robot.hasCollision}"^^xsd:boolean .
        <${robotUri}> robo:distanceToNearest "${distToNearest}"^^xsd:float .
        <${robotUri}> robo:distanceToObstacle "${distToObstacle}"^^xsd:float .
        <${robotUri}> robo:coverageArea "${known.coverageArea}"^^xsd:float .
        <${robotUri}> robo:pathKnottiness "${known.pathKnottiness}"^^xsd:float .
        <${robotUri}> robo:recentPositionCount "${known.recentPositions.length}"^^xsd:integer .
        <${robotUri}> robo:inLoop "${known.loopDetected}"^^xsd:boolean .
        <${robotUri}> robo:stuckCounter "${known.stuckCounter}"^^xsd:integer .
      }
      WHERE {
        OPTIONAL { <${robotUri}> robo:positionX ?oldX }
        OPTIONAL { <${robotUri}> robo:positionY ?oldY }
        OPTIONAL { <${robotUri}> robo:heading ?oldH }
        OPTIONAL { <${robotUri}> robo:batteryLevel ?oldB }
        OPTIONAL { <${robotUri}> robo:hasCollision ?oldC }
        OPTIONAL { <${robotUri}> robo:distanceToNearest ?oldDN }
        OPTIONAL { <${robotUri}> robo:distanceToObstacle ?oldDO }
        OPTIONAL { <${robotUri}> robo:coverageArea ?oldCA }
        OPTIONAL { <${robotUri}> robo:pathKnottiness ?oldPK }
        OPTIONAL { <${robotUri}> robo:recentPositionCount ?oldRPC }
        OPTIONAL { <${robotUri}> robo:inLoop ?oldIL }
        OPTIONAL { <${robotUri}> robo:stuckCounter ?oldSC }
      }
    `);
  }

  /**
   * Query robot state from ontology.
   */
  queryRobotState(robotId: string): RobotState {
    const robotUri = `urn:robot:${robotId}`;

    const results = this.store.query(`
      PREFIX robo: <${ROBO}>

      SELECT ?battery ?distNearest ?distObs ?collision ?inLoop ?coverageArea ?pathKnottiness ?recentCount ?stuckCounter
      WHERE {
        <${robotUri}> a robo:Robot .
        OPTIONAL { <${robotUri}> robo:batteryLevel ?battery }
        OPTIONAL { <${robotUri}> robo:distanceToNearest ?distNearest }
        OPTIONAL { <${robotUri}> robo:distanceToObstacle ?distObs }
        OPTIONAL { <${robotUri}> robo:hasCollision ?collision }
        OPTIONAL { <${robotUri}> robo:inLoop ?inLoop }
        OPTIONAL { <${robotUri}> robo:coverageArea ?coverageArea }
        OPTIONAL { <${robotUri}> robo:pathKnottiness ?pathKnottiness }
        OPTIONAL { <${robotUri}> robo:recentPositionCount ?recentCount }
        OPTIONAL { <${robotUri}> robo:stuckCounter ?stuckCounter }
      }
      LIMIT 1
    `);

    // Results are Map<string, Term>[]
    const resultArray = results as Map<string, Term>[];
    const bindings = resultArray[0] || new Map<string, Term>();

    const battery = parseFloat(bindings.get("battery")?.value || "100");
    const distNearest = parseFloat(bindings.get("distNearest")?.value || "999");
    const distObs = parseFloat(bindings.get("distObs")?.value || "999");
    const collision = bindings.get("collision")?.value === "true";
    const inLoop = bindings.get("inLoop")?.value === "true";
    const coverageArea = parseFloat(bindings.get("coverageArea")?.value || "0");
    const pathKnottiness = parseFloat(bindings.get("pathKnottiness")?.value || "0");
    const recentCount = parseInt(bindings.get("recentCount")?.value || "0");

    // Apply inference rules
    const state = this.applyInferenceRules({
      collision,
      battery,
      distanceToNearest: distNearest,
      distanceToObstacle: distObs,
      pathBlocked: false,
      atObject: false,
      nearObject: false,
      lowBattery: false,
      mustAvoid: false,
      emergencyAvoid: false,
      inLoop,
      coverageArea,
      pathKnottiness,
      recentPositionCount: recentCount,
      smallCoverage: false,
      shouldVenture: false,
      severelyCircling: false,
    });

    return state;
  }

  /**
   * Apply SWRL-style inference rules using parameters from ontology.
   * All thresholds are queried from the ontology, not hardcoded.
   */
  private applyInferenceRules(state: RobotState): RobotState {
    const p = this.params.detection;

    // Rule: Low battery (threshold from ontology)
    state.lowBattery = state.battery < p.lowBatteryThreshold;

    // Rule: At object (threshold from ontology)
    state.atObject = state.distanceToNearest < p.atObjectDistance;

    // Rule: Near object (threshold from ontology)
    state.nearObject = state.distanceToNearest < p.nearObjectDistance;

    // Rule: Must avoid (threshold from ontology)
    state.mustAvoid = state.distanceToObstacle < p.mustAvoidDistance;

    // Rule: Emergency avoid (threshold from ontology)
    state.emergencyAvoid = state.distanceToObstacle < p.emergencyAvoidDistance;

    // Rule: Small coverage (thresholds from ontology)
    state.smallCoverage = state.coverageArea < p.smallCoverageThreshold &&
                          state.recentPositionCount >= p.minPositionsForDetection;

    // Rule: High knottiness indicates circling (threshold from ontology)
    const highKnottiness = state.pathKnottiness > p.highKnottinessThreshold;

    // Rule: Should venture - triggered by loop detection, small coverage, or high knottiness
    state.shouldVenture = state.inLoop ||
                          (state.smallCoverage && state.recentPositionCount >= p.minPositionsForDetection) ||
                          (highKnottiness && state.recentPositionCount >= p.minPositionsForDetection);

    // Rule: Severely circling (thresholds from ontology)
    state.severelyCircling =
      (state.coverageArea < p.severelyCoverageThreshold && state.recentPositionCount >= p.minPositionsForDetection) ||
      (state.pathKnottiness > p.veryHighKnottinessThreshold && state.recentPositionCount >= p.minPositionsForDetection);

    return state;
  }

  /**
   * Mark an object as collected.
   */
  markObjectCollected(objId: string): void {
    const objUri = `urn:object:${objId}`;

    this.store.update(`
      PREFIX robo: <${ROBO}>
      PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

      DELETE { <${objUri}> robo:collected ?old }
      INSERT { <${objUri}> robo:collected "true"^^xsd:boolean }
      WHERE { OPTIONAL { <${objUri}> robo:collected ?old } }
    `);
  }

  /**
   * Get all twins for display in the Ontology tab.
   */
  getAllTwins(): Array<{ type: string; id: string; properties: string }> {
    const twins: Array<{ type: string; id: string; properties: string }> = [];

    // Query robots
    const robots = this.store.query(`
      PREFIX robo: <${ROBO}>
      SELECT ?robot ?x ?y ?heading ?battery ?coverageArea ?inLoop
      WHERE {
        ?robot a robo:Robot .
        OPTIONAL { ?robot robo:positionX ?x }
        OPTIONAL { ?robot robo:positionY ?y }
        OPTIONAL { ?robot robo:heading ?heading }
        OPTIONAL { ?robot robo:batteryLevel ?battery }
        OPTIONAL { ?robot robo:coverageArea ?coverageArea }
        OPTIONAL { ?robot robo:inLoop ?inLoop }
      }
    `) as Map<string, Term>[];

    for (const r of robots) {
      const id = r.get("robot")?.value?.replace("urn:robot:", "") || "unknown";
      const props = `pos=(${parseFloat(r.get("x")?.value || "0").toFixed(1)},${parseFloat(r.get("y")?.value || "0").toFixed(1)}), heading=${parseFloat(r.get("heading")?.value || "0").toFixed(0)}°, battery=${parseFloat(r.get("battery")?.value || "100").toFixed(0)}%, area=${parseFloat(r.get("coverageArea")?.value || "0").toFixed(1)}`;
      twins.push({ type: "Robot", id, properties: props });
    }

    // Query objects
    const objects = this.store.query(`
      PREFIX robo: <${ROBO}>
      SELECT ?obj ?x ?y ?value ?collected
      WHERE {
        ?obj a robo:WorldObject .
        OPTIONAL { ?obj robo:positionX ?x }
        OPTIONAL { ?obj robo:positionY ?y }
        OPTIONAL { ?obj robo:value ?value }
        OPTIONAL { ?obj robo:collected ?collected }
      }
    `) as Map<string, Term>[];

    for (const o of objects) {
      const id = o.get("obj")?.value?.replace("urn:object:", "") || "unknown";
      const collected = o.get("collected")?.value === "true";
      const props = `pos=(${parseFloat(o.get("x")?.value || "0").toFixed(1)},${parseFloat(o.get("y")?.value || "0").toFixed(1)}), value=${parseFloat(o.get("value")?.value || "1").toFixed(1)}, ${collected ? "collected" : "available"}`;
      twins.push({ type: "Object", id, properties: props });
    }

    // Query obstacles
    const obstacles = this.store.query(`
      PREFIX robo: <${ROBO}>
      SELECT ?obs ?x ?y ?radius
      WHERE {
        ?obs a robo:Obstacle .
        OPTIONAL { ?obs robo:positionX ?x }
        OPTIONAL { ?obs robo:positionY ?y }
        OPTIONAL { ?obs robo:radius ?radius }
      }
    `) as Map<string, Term>[];

    for (const obs of obstacles) {
      const id = obs.get("obs")?.value?.replace("urn:obstacle:", "") || "unknown";
      const props = `pos=(${parseFloat(obs.get("x")?.value || "0").toFixed(1)},${parseFloat(obs.get("y")?.value || "0").toFixed(1)}), radius=${parseFloat(obs.get("radius")?.value || "1").toFixed(1)}`;
      twins.push({ type: "Obstacle", id, properties: props });
    }

    return twins;
  }

  /**
   * Execute a raw SPARQL query.
   */
  query(sparql: string): unknown[] {
    return this.store.query(sparql) as unknown[];
  }

  /**
   * Dynamically query all configuration instances and their properties from the ontology.
   * This is truly ontology-driven - no hardcoded property names.
   */
  getAllConfigurations(): Array<{ configType: string; configId: string; properties: Array<{ name: string; value: string }> }> {
    const configs: Array<{ configType: string; configId: string; properties: Array<{ name: string; value: string }> }> = [];

    // Query all instances of BehaviorConfig subclasses with their properties
    const results = this.store.query(`
      PREFIX robo: <${ROBO}>
      PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
      PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

      SELECT ?config ?configType ?prop ?value ?label
      WHERE {
        ?config a ?configType .
        ?configType rdfs:subClassOf* robo:BehaviorConfig .
        ?config ?prop ?value .
        FILTER(?prop != rdf:type)
        FILTER(?prop != rdfs:label)
        OPTIONAL { ?config rdfs:label ?label }
      }
      ORDER BY ?configType ?config ?prop
    `) as Map<string, Term>[];

    // Group by config instance
    const configMap = new Map<string, { configType: string; label: string; properties: Array<{ name: string; value: string }> }>();

    for (const r of results) {
      const configUri = r.get("config")?.value || "";
      const configType = r.get("configType")?.value?.replace(ROBO, "") || "Config";
      const propUri = r.get("prop")?.value || "";
      const propName = propUri.replace(ROBO, "");
      const value = r.get("value")?.value || "";
      const label = r.get("label")?.value || configUri.replace(ROBO, "");

      if (!configMap.has(configUri)) {
        configMap.set(configUri, { configType, label, properties: [] });
      }
      configMap.get(configUri)!.properties.push({ name: propName, value });
    }

    for (const [_configId, data] of configMap) {
      configs.push({
        configType: data.configType,
        configId: data.label,
        properties: data.properties,
      });
    }

    return configs;
  }

  /**
   * Query all classes defined in the ontology (TBox).
   */
  getAllClasses(): string[] {
    const results = this.store.query(`
      PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
      PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
      PREFIX owl: <http://www.w3.org/2002/07/owl#>
      PREFIX robo: <${ROBO}>

      SELECT DISTINCT ?class
      WHERE {
        { ?class rdf:type owl:Class }
        UNION
        { ?class rdf:type rdfs:Class }
      }
      ORDER BY ?class
    `) as Map<string, Term>[];

    return results
      .map(r => r.get("class")?.value?.replace(ROBO, "") || "")
      .filter(c => c && !c.startsWith("http"));
  }

  /**
   * Query all properties defined in the ontology (TBox).
   */
  getAllProperties(): Array<{ name: string; type: string }> {
    const results = this.store.query(`
      PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
      PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
      PREFIX owl: <http://www.w3.org/2002/07/owl#>
      PREFIX robo: <${ROBO}>

      SELECT DISTINCT ?prop ?propType
      WHERE {
        { ?prop rdf:type owl:DatatypeProperty . BIND("DataProperty" AS ?propType) }
        UNION
        { ?prop rdf:type owl:ObjectProperty . BIND("ObjectProperty" AS ?propType) }
        UNION
        { ?prop rdf:type rdf:Property . BIND("Property" AS ?propType) }
      }
      ORDER BY ?prop
    `) as Map<string, Term>[];

    return results
      .map(r => ({
        name: r.get("prop")?.value?.replace(ROBO, "") || "",
        type: r.get("propType")?.value || "Property"
      }))
      .filter(p => p.name && !p.name.startsWith("http"));
  }

  /**
   * Query all inference rules defined in the ontology.
   */
  getAllRules(): Array<{ id: string; name: string; condition: string; conclusion: string; priority: number }> {
    const results = this.store.query(`
      PREFIX robo: <${ROBO}>
      PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

      SELECT ?rule ?label ?condition ?conclusion ?priority
      WHERE {
        ?rule a robo:InferenceRule .
        OPTIONAL { ?rule rdfs:label ?label }
        OPTIONAL { ?rule robo:ruleCondition ?condition }
        OPTIONAL { ?rule robo:ruleConclusion ?conclusion }
        OPTIONAL { ?rule robo:rulePriority ?priority }
      }
      ORDER BY ?priority
    `) as Map<string, Term>[];

    return results.map(r => ({
      id: r.get("rule")?.value?.replace(ROBO, "") || "",
      name: r.get("label")?.value || "",
      condition: r.get("condition")?.value || "",
      conclusion: r.get("conclusion")?.value || "",
      priority: parseInt(r.get("priority")?.value || "0"),
    }));
  }
}
