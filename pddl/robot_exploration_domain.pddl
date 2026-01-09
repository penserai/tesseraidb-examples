;; =============================================================================
;; Robot Exploration Domain
;; =============================================================================
;;
;; This PDDL domain defines the actions and constraints for autonomous robot
;; exploration in a grid-based environment. It is designed to work alongside
;; the robot_simulation.ttl ontology.
;;
;; Key concepts:
;;   - Robots navigate a grid, collecting objects while managing battery
;;   - Exploration prioritizes unexplored areas and quadrant coverage
;;   - Low battery triggers return-to-base behavior
;;   - Obstacles block movement
;;
;; Mapping to Ontology:
;;   PDDL Type/Predicate     | Ontology Class/Property
;;   ------------------------|----------------------------------
;;   robot                   | robo:Robot
;;   cell                    | Grid coordinates (x, y)
;;   object                  | robo:Object
;;   (at ?r ?c)              | robo:positionX, robo:positionY
;;   (battery ?r)            | robo:batteryLevel
;;   (collected ?o)          | robo:isCollected
;;   (explored ?r ?c)        | Tracked in robo:KnownWorld
;;
;; =============================================================================

(define (domain robot-exploration)
  (:requirements
    :strips                  ; Basic STRIPS planning
    :typing                  ; Typed parameters
    :numeric-fluents         ; Numeric state variables (battery, counts)
    :negative-preconditions  ; Negation in preconditions
  )

  ;; ===========================================================================
  ;; TYPES
  ;; ===========================================================================
  (:types
    robot - entity           ; Autonomous exploration agent
    cell - location          ; Grid position
    object - collectible     ; Item to be collected
    quadrant - region        ; NE, NW, SE, SW for exploration diversity
  )

  ;; ===========================================================================
  ;; PREDICATES (Boolean State)
  ;; ===========================================================================
  (:predicates
    ;; --- Spatial State ---
    (at ?r - robot ?c - cell)
    ;; Robot ?r is located at cell ?c

    (adjacent ?c1 - cell ?c2 - cell)
    ;; Cell ?c1 is adjacent to cell ?c2 (4-connected grid)

    (obstacle ?c - cell)
    ;; Cell ?c contains an impassable obstacle

    (base ?c - cell)
    ;; Cell ?c is a charging base station

    ;; --- Object State ---
    (object-at ?o - object ?c - cell)
    ;; Object ?o is located at cell ?c

    (collected ?o - object)
    ;; Object ?o has been collected by some robot

    ;; --- Exploration State ---
    (explored ?r - robot ?c - cell)
    ;; Robot ?r has visited cell ?c

    (in-quadrant ?c - cell ?q - quadrant)
    ;; Cell ?c belongs to quadrant ?q

    (visited-quadrant ?r - robot ?q - quadrant)
    ;; Robot ?r has explored at least one cell in quadrant ?q

    ;; --- Robot Status Flags ---
    (low-battery ?r - robot)
    ;; Robot ?r has battery below threshold (from ontology parameter)

    (at-base ?r - robot)
    ;; Robot ?r is currently at a base station
  )

  ;; ===========================================================================
  ;; NUMERIC FLUENTS (Continuous State)
  ;; ===========================================================================
  (:functions
    ;; --- Per-Robot State ---
    (battery ?r - robot)
    ;; Current battery level (0-100)

    (objects-collected ?r - robot)
    ;; Count of objects collected by robot ?r

    ;; --- Per-Cell State ---
    (exploration-priority ?c - cell)
    ;; Priority score for exploring cell ?c
    ;; Computed from ontology parameters:
    ;;   - unexplored-bonus if not yet visited
    ;;   - quadrant-crossing-bonus if in different quadrant
    ;;   - distance factors

    ;; --- Global Constants (from Ontology) ---
    (low-battery-threshold)
    ;; Battery level below which robot must return to base
    ;; Loaded from robo:DetectionConfig.lowBatteryThreshold

    (battery-drain-rate)
    ;; Battery consumed per move action
    ;; Loaded from robo:ActionConfig.batteryDrainRate
  )

  ;; ===========================================================================
  ;; ACTIONS
  ;; ===========================================================================

  ;; ---------------------------------------------------------------------------
  ;; ACTION: move
  ;; ---------------------------------------------------------------------------
  ;; Move robot to an adjacent cell.
  ;;
  ;; Preconditions:
  ;;   - Robot is at the source cell
  ;;   - Source and destination are adjacent
  ;;   - Destination is not an obstacle
  ;;   - Robot has battery remaining
  ;;   - Robot is not in low-battery state
  ;;
  ;; Effects:
  ;;   - Robot is now at destination
  ;;   - Robot is no longer at source
  ;;   - Destination is marked as explored
  ;;   - Battery decreases
  ;; ---------------------------------------------------------------------------
  (:action move
    :parameters (?r - robot ?from - cell ?to - cell)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (> (battery ?r) (battery-drain-rate))
      (not (low-battery ?r))
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (explored ?r ?to)
      (not (at-base ?r))
      (decrease (battery ?r) (battery-drain-rate))
    )
  )

  ;; ---------------------------------------------------------------------------
  ;; ACTION: collect
  ;; ---------------------------------------------------------------------------
  ;; Collect an object at the robot's current location.
  ;;
  ;; Preconditions:
  ;;   - Robot is at the object's location
  ;;   - Object has not been collected yet
  ;;
  ;; Effects:
  ;;   - Object is marked as collected
  ;;   - Object is no longer at the cell
  ;;   - Robot's collection count increases
  ;; ---------------------------------------------------------------------------
  (:action collect
    :parameters (?r - robot ?c - cell ?o - object)
    :precondition (and
      (at ?r ?c)
      (object-at ?o ?c)
      (not (collected ?o))
    )
    :effect (and
      (collected ?o)
      (not (object-at ?o ?c))
      (increase (objects-collected ?r) 1)
    )
  )

  ;; ---------------------------------------------------------------------------
  ;; ACTION: explore
  ;; ---------------------------------------------------------------------------
  ;; Move toward an unexplored high-priority cell.
  ;; Similar to move but requires the destination to be unexplored.
  ;;
  ;; Preconditions:
  ;;   - Robot is at the source cell
  ;;   - Destination is adjacent and not an obstacle
  ;;   - Destination has NOT been explored by this robot
  ;;   - Destination is in some quadrant
  ;;   - Robot has sufficient battery
  ;;
  ;; Effects:
  ;;   - Same as move, plus marks quadrant as visited
  ;; ---------------------------------------------------------------------------
  (:action explore
    :parameters (?r - robot ?from - cell ?to - cell ?q - quadrant)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (explored ?r ?to))
      (in-quadrant ?to ?q)
      (> (battery ?r) (battery-drain-rate))
      (not (low-battery ?r))
      (> (exploration-priority ?to) 0)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (explored ?r ?to)
      (visited-quadrant ?r ?q)
      (not (at-base ?r))
      (decrease (battery ?r) (battery-drain-rate))
    )
  )

  ;; ---------------------------------------------------------------------------
  ;; ACTION: return-to-base
  ;; ---------------------------------------------------------------------------
  ;; Move toward a base station when battery is low.
  ;;
  ;; Preconditions:
  ;;   - Robot is at some cell
  ;;   - Destination is adjacent
  ;;   - Destination is not an obstacle
  ;;   - Robot has low battery flag set
  ;;
  ;; Effects:
  ;;   - Robot moves to destination
  ;;   - If destination is a base, battery is recharged
  ;; ---------------------------------------------------------------------------
  (:action return-to-base
    :parameters (?r - robot ?from - cell ?to - cell)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (low-battery ?r)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (explored ?r ?to)
      (decrease (battery ?r) (battery-drain-rate))
    )
  )

  ;; ---------------------------------------------------------------------------
  ;; ACTION: recharge
  ;; ---------------------------------------------------------------------------
  ;; Recharge battery at a base station.
  ;;
  ;; Preconditions:
  ;;   - Robot is at a base cell
  ;;   - Robot has low battery
  ;;
  ;; Effects:
  ;;   - Battery is fully recharged
  ;;   - Low battery flag is cleared
  ;;   - Robot is marked as at-base
  ;; ---------------------------------------------------------------------------
  (:action recharge
    :parameters (?r - robot ?c - cell)
    :precondition (and
      (at ?r ?c)
      (base ?c)
      (low-battery ?r)
    )
    :effect (and
      (assign (battery ?r) 100)
      (not (low-battery ?r))
      (at-base ?r)
    )
  )

  ;; ---------------------------------------------------------------------------
  ;; ACTION: set-low-battery
  ;; ---------------------------------------------------------------------------
  ;; Triggered when battery drops below threshold.
  ;; This is a "sensing" action that updates the low-battery flag.
  ;;
  ;; Preconditions:
  ;;   - Battery is below threshold
  ;;   - Low battery flag is not already set
  ;;
  ;; Effects:
  ;;   - Low battery flag is set
  ;; ---------------------------------------------------------------------------
  (:action set-low-battery
    :parameters (?r - robot)
    :precondition (and
      (<= (battery ?r) (low-battery-threshold))
      (not (low-battery ?r))
    )
    :effect (and
      (low-battery ?r)
    )
  )
)
