(define (domain cobot_grid)
  (:requirements :typing :negative-preconditions :strips)
  (:types
    block cell dir
    red blue green - block
  )

  (:predicates
    (at ?b - block ?c - cell)
    (free ?c - cell)
    (goal ?r - red ?c - cell)
    (adjacent ?from ?to - cell ?d - dir)
  )

  (:action user_move_blue
    :parameters (?b - blue ?from - cell ?to - cell ?d - dir)
    :precondition (and (at ?b ?from) (free ?to) (adjacent ?from ?to ?d))
    :effect (and (at ?b ?to) (free ?from) (not (free ?to)) (not (at ?b ?from))))

  (:action user_move_green
    :parameters (?g - green ?from - cell ?to - cell ?d - dir)
    :precondition (and (at ?g ?from) (free ?to) (adjacent ?from ?to ?d))
    :effect (and (at ?g ?to) (free ?from) (not (free ?to)) (not (at ?g ?from))))

  (:action robot_move_green
    :parameters (?g - green ?from - cell ?to - cell ?d - dir)
    :precondition (and (at ?g ?from) (free ?to) (adjacent ?from ?to ?d))
    :effect (and (at ?g ?to) (free ?from) (not (free ?to)) (not (at ?g ?from))))

  (:action robot_move_red
    :parameters (?r - red ?from - cell ?to - cell ?d - dir)
    :precondition (and (at ?r ?from) (free ?to) (adjacent ?from ?to ?d))
    :effect (and (at ?r ?to) (free ?from) (not (free ?to)) (not (at ?r ?from))))
)
