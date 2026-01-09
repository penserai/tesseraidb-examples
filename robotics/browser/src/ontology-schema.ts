/**
 * Ontology Schema - Defines the TBox and default ABox for the robotics ontology.
 * All behavior parameters are stored here, making them queryable and language-agnostic.
 *
 * NOTE: This schema mirrors the shared ontology at:
 *   examples/ontologies/robot_simulation.ttl
 *
 * Both Python and TypeScript implementations use the same parameter definitions.
 * The namespace is aligned: http://tesserai.io/ontology/robot_simulation#
 */

export const ROBOTICS_ONTOLOGY_TURTLE = `
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix robo: <http://tesserai.io/ontology/robot_simulation#> .

# =============================================================================
# CLASSES (TBox)
# =============================================================================

# Core entity classes
robo:Robot rdf:type owl:Class ;
    rdfs:label "Robot" ;
    rdfs:comment "An autonomous robot agent in the simulation" .

robo:WorldObject rdf:type owl:Class ;
    rdfs:label "World Object" ;
    rdfs:comment "A collectible object in the world" .

robo:Obstacle rdf:type owl:Class ;
    rdfs:label "Obstacle" ;
    rdfs:comment "An impassable obstacle" .

# State classification classes (inferred by rules)
robo:CollisionState rdf:type owl:Class ;
    rdfs:label "Collision State" ;
    rdfs:comment "Robot has collided with something" .

robo:LowBattery rdf:type owl:Class ;
    rdfs:label "Low Battery" ;
    rdfs:comment "Robot battery is below threshold" .

robo:AtObject rdf:type owl:Class ;
    rdfs:label "At Object" ;
    rdfs:comment "Robot is close enough to collect object" .

robo:NearObject rdf:type owl:Class ;
    rdfs:label "Near Object" ;
    rdfs:comment "Robot can sense a nearby object" .

robo:MustAvoid rdf:type owl:Class ;
    rdfs:label "Must Avoid" ;
    rdfs:comment "Robot must avoid obstacle" .

robo:EmergencyAvoid rdf:type owl:Class ;
    rdfs:label "Emergency Avoid" ;
    rdfs:comment "Robot in emergency avoidance mode" .

robo:InLoop rdf:type owl:Class ;
    rdfs:label "In Loop" ;
    rdfs:comment "Robot is stuck in a loop pattern" .

robo:SmallCoverage rdf:type owl:Class ;
    rdfs:label "Small Coverage" ;
    rdfs:comment "Robot covering small area despite movement" .

robo:ShouldVenture rdf:type owl:Class ;
    rdfs:label "Should Venture" ;
    rdfs:comment "Robot should venture to new areas" .

robo:SeverelyCircling rdf:type owl:Class ;
    rdfs:label "Severely Circling" ;
    rdfs:comment "Robot is severely stuck in circular pattern" .

# Configuration classes
robo:BehaviorConfig rdf:type owl:Class ;
    rdfs:label "Behavior Configuration" ;
    rdfs:comment "Configuration parameters for robot behavior" .

robo:ExplorationConfig rdf:type owl:Class ;
    rdfs:subClassOf robo:BehaviorConfig ;
    rdfs:label "Exploration Configuration" ;
    rdfs:comment "Parameters for exploration scoring" .

robo:EscapeConfig rdf:type owl:Class ;
    rdfs:subClassOf robo:BehaviorConfig ;
    rdfs:label "Escape Configuration" ;
    rdfs:comment "Parameters for escape behavior" .

robo:DetectionConfig rdf:type owl:Class ;
    rdfs:subClassOf robo:BehaviorConfig ;
    rdfs:label "Detection Configuration" ;
    rdfs:comment "Thresholds for state detection" .

robo:ActionConfig rdf:type owl:Class ;
    rdfs:subClassOf robo:BehaviorConfig ;
    rdfs:label "Action Configuration" ;
    rdfs:comment "Parameters for action execution" .

# =============================================================================
# PROPERTIES (TBox)
# =============================================================================

# Robot state properties
robo:positionX rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:float .

robo:positionY rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:float .

robo:heading rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:float .

robo:batteryLevel rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:float .

robo:hasCollision rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:boolean .

robo:distanceToNearest rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:float .

robo:distanceToObstacle rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:float .

robo:coverageArea rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:float .

robo:pathKnottiness rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:float .

robo:recentPositionCount rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:integer .

robo:inLoop rdf:type owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:boolean .

# =============================================================================
# EXPLORATION SCORING PARAMETERS (ABox - Configuration Instance)
# =============================================================================

robo:DefaultExplorationConfig rdf:type robo:ExplorationConfig ;
    rdfs:label "Default Exploration Configuration" ;

    # Quadrant-based scoring (encourages crossing the grid)
    robo:quadrantCrossingBonus "40.0"^^xsd:float ;
    robo:sameQuadrantPenalty "20.0"^^xsd:float ;

    # Center-seeking when at edges
    robo:centerApproachBonus "30.0"^^xsd:float ;
    robo:edgeDistanceThreshold "0.3"^^xsd:float ;

    # Unexplored area bonuses
    robo:unexploredTargetBonus "25.0"^^xsd:float ;
    robo:unexploredPathBonus "10.0"^^xsd:float ;

    # Distance bonus (encourages going far)
    robo:distanceBonusMultiplier "0.5"^^xsd:float ;

    # Exploration calculation
    robo:directionSampleCount "24"^^xsd:integer ;
    robo:ventureDistanceFactor "2.5"^^xsd:float ;
    robo:gridMarginFactor "0.1"^^xsd:float .

# =============================================================================
# ESCAPE BEHAVIOR PARAMETERS (ABox - Configuration Instance)
# =============================================================================

robo:DefaultEscapeConfig rdf:type robo:EscapeConfig ;
    rdfs:label "Default Escape Configuration" ;

    # Escape direction calculation
    robo:escapeAngleVariance "90.0"^^xsd:float ;
    robo:escapeBaseAngleOffset "180.0"^^xsd:float ;

    # Escape duration and distance
    robo:escapeTickDuration "25"^^xsd:integer ;
    robo:escapeMinDistance "12.0"^^xsd:float ;
    robo:escapeDistanceFactor "3.0"^^xsd:float ;

    # Escape completion thresholds
    robo:escapeTargetReachedDistance "2.0"^^xsd:float ;
    robo:escapeClutterClearDistance "12.0"^^xsd:float .

# =============================================================================
# DETECTION THRESHOLDS (ABox - Configuration Instance)
# =============================================================================

robo:DefaultDetectionConfig rdf:type robo:DetectionConfig ;
    rdfs:label "Default Detection Configuration" ;

    # Battery thresholds
    robo:lowBatteryThreshold "20.0"^^xsd:float ;
    robo:batteryDrainRate "0.05"^^xsd:float ;

    # Object detection distances
    robo:atObjectDistance "1.0"^^xsd:float ;
    robo:nearObjectDistance "3.0"^^xsd:float ;

    # Obstacle avoidance distances
    robo:mustAvoidDistance "1.5"^^xsd:float ;
    robo:emergencyAvoidDistance "0.8"^^xsd:float ;

    # Loop detection thresholds
    robo:smallCoverageThreshold "15.0"^^xsd:float ;
    robo:severelyCoverageThreshold "8.0"^^xsd:float ;
    robo:highKnottinessThreshold "9.42"^^xsd:float ;
    robo:veryHighKnottinessThreshold "18.84"^^xsd:float ;
    robo:minPositionsForDetection "10"^^xsd:integer ;
    robo:lowUniqueCellsRatio "0.4"^^xsd:float ;
    robo:repeatedVisitThreshold "3"^^xsd:integer .

# =============================================================================
# ACTION PARAMETERS (ABox - Configuration Instance)
# =============================================================================

robo:DefaultActionConfig rdf:type robo:ActionConfig ;
    rdfs:label "Default Action Configuration" ;

    # Movement parameters
    robo:defaultSpeed "1.0"^^xsd:float ;
    robo:turnRateExplore "25.0"^^xsd:float ;
    robo:turnRateDirect "90.0"^^xsd:float ;

    # Obstacle avoidance
    robo:avoidanceCheckDistance "2.0"^^xsd:float ;
    robo:collisionBuffer "0.3"^^xsd:float ;
    robo:obstacleBuffer "0.5"^^xsd:float ;
    robo:avoidanceJitter "20.0"^^xsd:float ;
    robo:turnAroundJitter "90.0"^^xsd:float ;

    # World boundaries
    robo:worldBoundaryMargin "3.0"^^xsd:float .

# =============================================================================
# SWRL-STYLE INFERENCE RULES (stored as data, interpreted by reasoner)
# =============================================================================

robo:Rule_LowBattery rdf:type robo:InferenceRule ;
    rdfs:label "Low Battery Rule" ;
    robo:ruleCondition "batteryLevel < lowBatteryThreshold" ;
    robo:ruleConclusion "LowBattery" ;
    robo:rulePriority "1"^^xsd:integer .

robo:Rule_AtObject rdf:type robo:InferenceRule ;
    rdfs:label "At Object Rule" ;
    robo:ruleCondition "distanceToNearest < atObjectDistance" ;
    robo:ruleConclusion "AtObject" ;
    robo:rulePriority "2"^^xsd:integer .

robo:Rule_NearObject rdf:type robo:InferenceRule ;
    rdfs:label "Near Object Rule" ;
    robo:ruleCondition "distanceToNearest < nearObjectDistance" ;
    robo:ruleConclusion "NearObject" ;
    robo:rulePriority "3"^^xsd:integer .

robo:Rule_MustAvoid rdf:type robo:InferenceRule ;
    rdfs:label "Must Avoid Rule" ;
    robo:ruleCondition "distanceToObstacle < mustAvoidDistance" ;
    robo:ruleConclusion "MustAvoid" ;
    robo:rulePriority "4"^^xsd:integer .

robo:Rule_EmergencyAvoid rdf:type robo:InferenceRule ;
    rdfs:label "Emergency Avoid Rule" ;
    robo:ruleCondition "distanceToObstacle < emergencyAvoidDistance" ;
    robo:ruleConclusion "EmergencyAvoid" ;
    robo:rulePriority "5"^^xsd:integer .

robo:Rule_SmallCoverage rdf:type robo:InferenceRule ;
    rdfs:label "Small Coverage Rule" ;
    robo:ruleCondition "coverageArea < smallCoverageThreshold AND recentPositionCount >= minPositionsForDetection" ;
    robo:ruleConclusion "SmallCoverage" ;
    robo:rulePriority "6"^^xsd:integer .

robo:Rule_SeverelyCircling rdf:type robo:InferenceRule ;
    rdfs:label "Severely Circling Rule" ;
    robo:ruleCondition "coverageArea < severelyCoverageThreshold OR pathKnottiness > veryHighKnottinessThreshold" ;
    robo:ruleConclusion "SeverelyCircling" ;
    robo:rulePriority "7"^^xsd:integer .

robo:Rule_ShouldVenture rdf:type robo:InferenceRule ;
    rdfs:label "Should Venture Rule" ;
    robo:ruleCondition "inLoop OR SmallCoverage OR (pathKnottiness > highKnottinessThreshold AND recentPositionCount >= minPositionsForDetection)" ;
    robo:ruleConclusion "ShouldVenture" ;
    robo:rulePriority "8"^^xsd:integer .
`;

/**
 * Interface for all behavior parameters queried from ontology.
 * Any language implementation should query these same parameters.
 */
export interface BehaviorParameters {
  // Exploration scoring
  exploration: {
    quadrantCrossingBonus: number;
    sameQuadrantPenalty: number;
    centerApproachBonus: number;
    edgeDistanceThreshold: number;
    unexploredTargetBonus: number;
    unexploredPathBonus: number;
    distanceBonusMultiplier: number;
    directionSampleCount: number;
    ventureDistanceFactor: number;
    gridMarginFactor: number;
  };

  // Escape behavior
  escape: {
    angleVariance: number;
    baseAngleOffset: number;
    tickDuration: number;
    minDistance: number;
    distanceFactor: number;
    targetReachedDistance: number;
    clutterClearDistance: number;
  };

  // Detection thresholds
  detection: {
    lowBatteryThreshold: number;
    batteryDrainRate: number;
    atObjectDistance: number;
    nearObjectDistance: number;
    mustAvoidDistance: number;
    emergencyAvoidDistance: number;
    smallCoverageThreshold: number;
    severelyCoverageThreshold: number;
    highKnottinessThreshold: number;
    veryHighKnottinessThreshold: number;
    minPositionsForDetection: number;
    lowUniqueCellsRatio: number;
    repeatedVisitThreshold: number;
  };

  // Action parameters
  action: {
    defaultSpeed: number;
    turnRateExplore: number;
    turnRateDirect: number;
    avoidanceCheckDistance: number;
    collisionBuffer: number;
    obstacleBuffer: number;
    avoidanceJitter: number;
    turnAroundJitter: number;
    worldBoundaryMargin: number;
  };
}

/**
 * SPARQL query to load all behavior parameters from the ontology.
 * This query is language-agnostic - same query works in Python, Rust, etc.
 */
export const LOAD_PARAMETERS_QUERY = `
PREFIX robo: <http://tesserai.io/ontology/robot_simulation#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT
  # Exploration parameters
  ?quadrantCrossingBonus ?sameQuadrantPenalty ?centerApproachBonus
  ?edgeDistanceThreshold ?unexploredTargetBonus ?unexploredPathBonus
  ?distanceBonusMultiplier ?directionSampleCount ?ventureDistanceFactor
  ?gridMarginFactor

  # Escape parameters
  ?escapeAngleVariance ?escapeBaseAngleOffset ?escapeTickDuration
  ?escapeMinDistance ?escapeDistanceFactor ?escapeTargetReachedDistance
  ?escapeClutterClearDistance

  # Detection parameters
  ?lowBatteryThreshold ?batteryDrainRate ?atObjectDistance ?nearObjectDistance
  ?mustAvoidDistance ?emergencyAvoidDistance ?smallCoverageThreshold
  ?severelyCoverageThreshold ?highKnottinessThreshold ?veryHighKnottinessThreshold
  ?minPositionsForDetection ?lowUniqueCellsRatio ?repeatedVisitThreshold

  # Action parameters
  ?defaultSpeed ?turnRateExplore ?turnRateDirect ?avoidanceCheckDistance
  ?collisionBuffer ?obstacleBuffer ?avoidanceJitter ?turnAroundJitter
  ?worldBoundaryMargin

WHERE {
  # Exploration config
  ?exploreConfig a robo:ExplorationConfig .
  ?exploreConfig robo:quadrantCrossingBonus ?quadrantCrossingBonus .
  ?exploreConfig robo:sameQuadrantPenalty ?sameQuadrantPenalty .
  ?exploreConfig robo:centerApproachBonus ?centerApproachBonus .
  ?exploreConfig robo:edgeDistanceThreshold ?edgeDistanceThreshold .
  ?exploreConfig robo:unexploredTargetBonus ?unexploredTargetBonus .
  ?exploreConfig robo:unexploredPathBonus ?unexploredPathBonus .
  ?exploreConfig robo:distanceBonusMultiplier ?distanceBonusMultiplier .
  ?exploreConfig robo:directionSampleCount ?directionSampleCount .
  ?exploreConfig robo:ventureDistanceFactor ?ventureDistanceFactor .
  ?exploreConfig robo:gridMarginFactor ?gridMarginFactor .

  # Escape config
  ?escapeConfig a robo:EscapeConfig .
  ?escapeConfig robo:escapeAngleVariance ?escapeAngleVariance .
  ?escapeConfig robo:escapeBaseAngleOffset ?escapeBaseAngleOffset .
  ?escapeConfig robo:escapeTickDuration ?escapeTickDuration .
  ?escapeConfig robo:escapeMinDistance ?escapeMinDistance .
  ?escapeConfig robo:escapeDistanceFactor ?escapeDistanceFactor .
  ?escapeConfig robo:escapeTargetReachedDistance ?escapeTargetReachedDistance .
  ?escapeConfig robo:escapeClutterClearDistance ?escapeClutterClearDistance .

  # Detection config
  ?detectConfig a robo:DetectionConfig .
  ?detectConfig robo:lowBatteryThreshold ?lowBatteryThreshold .
  ?detectConfig robo:batteryDrainRate ?batteryDrainRate .
  ?detectConfig robo:atObjectDistance ?atObjectDistance .
  ?detectConfig robo:nearObjectDistance ?nearObjectDistance .
  ?detectConfig robo:mustAvoidDistance ?mustAvoidDistance .
  ?detectConfig robo:emergencyAvoidDistance ?emergencyAvoidDistance .
  ?detectConfig robo:smallCoverageThreshold ?smallCoverageThreshold .
  ?detectConfig robo:severelyCoverageThreshold ?severelyCoverageThreshold .
  ?detectConfig robo:highKnottinessThreshold ?highKnottinessThreshold .
  ?detectConfig robo:veryHighKnottinessThreshold ?veryHighKnottinessThreshold .
  ?detectConfig robo:minPositionsForDetection ?minPositionsForDetection .
  ?detectConfig robo:lowUniqueCellsRatio ?lowUniqueCellsRatio .
  ?detectConfig robo:repeatedVisitThreshold ?repeatedVisitThreshold .

  # Action config
  ?actionConfig a robo:ActionConfig .
  ?actionConfig robo:defaultSpeed ?defaultSpeed .
  ?actionConfig robo:turnRateExplore ?turnRateExplore .
  ?actionConfig robo:turnRateDirect ?turnRateDirect .
  ?actionConfig robo:avoidanceCheckDistance ?avoidanceCheckDistance .
  ?actionConfig robo:collisionBuffer ?collisionBuffer .
  ?actionConfig robo:obstacleBuffer ?obstacleBuffer .
  ?actionConfig robo:avoidanceJitter ?avoidanceJitter .
  ?actionConfig robo:turnAroundJitter ?turnAroundJitter .
  ?actionConfig robo:worldBoundaryMargin ?worldBoundaryMargin .
}
`;
