;; =============================================================================
;; Robot Exploration Domain (STRIPS version)
;; =============================================================================
;;
;; A simplified STRIPS version of the robot exploration domain that works with
;; the SimplePlanner. This version does NOT use numeric fluents.
;;
;; Limitations vs. full domain:
;;   - No battery tracking (use low-battery flag instead)
;;   - No object collection counts
;;   - No exploration priority scores
;;
;; =============================================================================

(define (domain robot-exploration-strips)
  (:requirements :strips :typing :negative-preconditions)

  (:types
    robot
    location
    object
  )

  (:predicates
    ;; Spatial state
    (at ?r - robot ?l - location)
    (adjacent ?l1 - location ?l2 - location)
    (obstacle ?l - location)
    (base ?l - location)

    ;; Object state
    (object-at ?o - object ?l - location)
    (collected ?o - object)
    (carrying ?r - robot ?o - object)

    ;; Robot state
    (low-battery ?r - robot)
    (at-base ?r - robot)
    (explored ?r - robot ?l - location)
  )

  ;; ---------------------------------------------------------------------------
  ;; ACTION: move
  ;; ---------------------------------------------------------------------------
  ;; Move robot to an adjacent cell.
  ;; ---------------------------------------------------------------------------
  (:action move
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (low-battery ?r))
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (explored ?r ?to)
      (not (at-base ?r))
    )
  )

  ;; ---------------------------------------------------------------------------
  ;; ACTION: collect
  ;; ---------------------------------------------------------------------------
  ;; Pick up an object at the robot's current location.
  ;; ---------------------------------------------------------------------------
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

  ;; ---------------------------------------------------------------------------
  ;; ACTION: return-to-base
  ;; ---------------------------------------------------------------------------
  ;; Move toward base when battery is low.
  ;; ---------------------------------------------------------------------------
  (:action return-to-base
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (low-battery ?r)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
    )
  )

  ;; ---------------------------------------------------------------------------
  ;; ACTION: recharge
  ;; ---------------------------------------------------------------------------
  ;; Recharge at base station.
  ;; ---------------------------------------------------------------------------
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
)
