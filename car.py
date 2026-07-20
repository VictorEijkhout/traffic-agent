"""
car.py

Defines the Car agent. A car lives on a StreetGrid, moves along the
street it's currently on, and keeps a safe distance from the car ahead
of it using a simple car-following ("adaptive cruise control") rule:

    desired_speed = clamp(gap_to_car_ahead - safety_gap, 0, max_speed)

and then eases its actual speed toward that desired speed subject to a
maximum acceleration/deceleration, so it doesn't teleport-brake.

At intersections a car picks a new heading at random from the legal
directions available at that point (straight on, or turning onto the
crossing street), which is enough to get interesting traffic behavior
without a routing/pathfinding layer.

A Car's movement is split into `plan()` (side-effect-free: figure out
what it *would* do) and `apply_move()` (actually do it). That split lets
simulation.step_all() collect every car's intended move for the tick,
resolve right-of-way between cars converging on the same intersection
(standard "yield to the right" rule), and only then move anyone -- so
two cars can never end up occupying, or crossing through, the same
intersection cell in the same tick.

Streets are bidirectional: each direction of travel is treated as its
own lane, so a car heading straight toward you on an ordinary stretch of
street is in the other lane and isn't an obstacle -- it's what lets two
cars pass each other instead of meeting nose-to-nose and freezing there
forever. The one place lanes still merge is the intersection point
itself, which this simplified grid models as a single shared coordinate
rather than separate crossing lanes; a car sitting right there is still
an obstacle to everyone, regardless of its heading.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

Direction = Tuple[int, int]  # one of (1,0), (-1,0), (0,1), (0,-1)

DIRECTION_ARROWS = {
    (1, 0): ">",
    (-1, 0): "<",
    (0, 1): "v",
    (0, -1): "^",
}

# VT100/ANSI SGR foreground color codes used to tell cars apart on screen.
# Cars are assigned one of these in rotation as they're created; standard
# (not bright) colors, since bright/background colors are less portable
# across terminals.
CAR_COLORS = [31, 32, 33, 34, 35, 36]  # red, green, yellow, blue, magenta, cyan


def rotate_left(direction: Direction) -> Direction:
    """
    Rotate a heading 90 degrees counter-clockwise as driven (i.e. the
    direction that would be "to the right" of someone facing the
    opposite way). Using (x right, y down) grid coordinates:
    East->North->West->South->East.
    """
    dx, dy = direction
    return (dy, -dx)


def yields_to(mover_direction: Direction, other_direction: Direction) -> bool:
    """
    Standard uncontrolled-intersection rule: a driver yields to whoever
    is approaching from their right. `other_direction` is "on the right"
    of `mover_direction` exactly when other_direction == rotate_left(mover_direction)
    (see the docstring on rotate_left for the coordinate convention).
    """
    return other_direction == rotate_left(mover_direction)


@dataclass
class Move:
    """A car's intended action for this tick, computed without mutating
    the car -- so several cars' moves can be planned first, conflicts
    among them resolved (right-of-way), and only then applied."""
    car: "Car"
    speed: float
    new_x: float
    new_y: float
    intersection_cell: Optional[Tuple[int, int]]  # set if this move enters an intersection this tick
    chosen_direction: Direction  # heading this car will have after the move (may differ from car.direction if turning)

    @property
    def enters_intersection(self) -> bool:
        return self.intersection_cell is not None


def _first_boundary_crossed(old: float, new: float, step: int) -> Optional[int]:
    """
    Given a move from `old` to `new` along one axis, where `step` is the
    sign of travel (+1 or -1), return the first integer strictly between
    `old` and `new` (in the direction of travel) that this move reaches
    or passes -- i.e. the street line actually crossed.

    This matters because two cars converging on the same intersection
    from opposite sides, at different speeds, can each end up with a
    `new` position on a different side of the intersection (e.g. 16.42
    approaching from the east, 16.83 approaching from the west) --
    simply rounding each one to its nearest integer can send them to two
    different cells (16 and 17) even though they're crossing the exact
    same physical intersection, which would let a real conflict slip
    past the right-of-way check entirely.
    """
    if step > 0:
        candidate = math.floor(old) + 1
        if candidate <= new + 1e-9:
            return candidate
    else:
        candidate = math.ceil(old) - 1
        if candidate >= new - 1e-9:
            return candidate
    return None


class Car:
    _next_id = 1

    def __init__(
        self,
        x: float,
        y: float,
        direction: Direction = (1, 0),
        max_speed: float = 1.0,
        safety_gap: float = 1.0,
        max_accel: float = 0.5,
        max_decel: float = 1.0,
        turn_probability: float = 0.35,
        artery_turn_probability: float = 0.03,
        car_id: Optional[str] = None,
    ):
        self.x = float(x)
        self.y = float(y)
        self.direction = direction
        self.speed = 0.0

        self.max_speed = max_speed
        self.safety_gap = safety_gap  # minimum bumper-to-bumper gap to keep
        self.max_accel = max_accel    # how fast it can speed up per tick
        self.max_decel = max_decel    # how fast it can brake per tick

        # probability of turning at an eligible intersection under normal
        # conditions, versus while currently traveling along a designated
        # major artery (kept much lower, so artery traffic mostly stays put)
        self.turn_probability = turn_probability
        self.artery_turn_probability = artery_turn_probability

        self.id = car_id or f"C{Car._next_id}"
        self.color = CAR_COLORS[Car._next_id % len(CAR_COLORS)]
        Car._next_id += 1

    # -- geometry --------------------------------------------------

    @property
    def position(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def _same_line(self, other: "Car", grid) -> bool:
        """
        True if `other` is an obstacle on the line this car is currently
        driving along: same row, if I'm moving horizontally, or same
        column, if I'm moving vertically.

        Each direction of travel counts as its own lane on a bidirectional
        street: a car heading straight toward me on an ordinary stretch
        of street is in the *other* lane, not mine, so it doesn't block
        me (this is what lets two cars pass each other instead of
        deadlocking nose-to-nose forever). Any other relationship --
        same direction, perpendicular, or stopped/turning -- still counts
        as an obstacle, same as before.

        The one place lanes necessarily merge back together in this
        simplified grid is the intersection point itself (it's a single
        shared coordinate, not two separate crossing lanes), so an
        oncoming car sitting right at an intersection is still treated as
        an obstacle -- that's what keeps a car that just turned from
        becoming briefly invisible to a car still arriving head-on.
        """
        if self.direction[0] != 0:  # moving horizontally -> compare row
            same_axis = abs(self.y - other.y) < 1e-6
        else:  # moving vertically -> compare column
            same_axis = abs(self.x - other.x) < 1e-6
        if not same_axis:
            return False

        oncoming = other.direction == (-self.direction[0], -self.direction[1])
        if not oncoming:
            return True
        return grid.is_intersection(self.x, self.y) or grid.is_intersection(other.x, other.y)

    def distance_ahead(
        self, other_cars: List["Car"], grid
    ) -> Tuple[Optional[float], bool]:
        """
        Distance (along the direction of travel) to the nearest car ahead
        of this one on the same line, accounting for toroidal wraparound,
        and whether that car is oncoming (heading directly toward me,
        rather than stopped, turning, or moving the same way).

        Returns (gap, oncoming); gap is None if there's no car ahead.
        """
        best = None
        best_oncoming = False
        dx, dy = self.direction
        span = grid.width if dx != 0 else grid.height
        my_pos = self.x if dx != 0 else self.y

        for other in other_cars:
            if other is self or not self._same_line(other, grid):
                continue
            other_pos = other.x if dx != 0 else other.y
            # signed forward distance, wrapped to [0, span)
            forward = (other_pos - my_pos) * (dx + dy)  # dx or dy is the +-1 component
            forward %= span
            if forward <= 1e-9:
                continue  # same spot or "behind" after wrap -> ignore
            if best is None or forward < best:
                best = forward
                best_oncoming = other.direction == (-dx, -dy)
        return best, best_oncoming

    # -- safe-distance / car-following rule -------------------------

    def safe_speed(self, gap: Optional[float], oncoming: bool = False) -> float:
        """
        The speed this car *should* be going given the gap to the car
        ahead (None = no car ahead / open road).

        If that car is oncoming, only half the available room is used as
        this car's budget for closing the gap: the other car will likely
        apply the exact same rule and close the other half, so splitting
        it is what keeps the *final* gap at safety_gap instead of both
        cars independently racing to close the whole thing and ending up
        right on top of each other.
        """
        if gap is None:
            return self.max_speed
        budget = gap - self.safety_gap
        if oncoming:
            budget /= 2
        return max(0.0, min(self.max_speed, budget))

    def plan(
        self,
        grid,
        other_cars: List["Car"],
        dt: float = 1.0,
        rng: Optional[random.Random] = None,
    ) -> Move:
        """
        Work out what this car *would* do this tick -- new speed and
        position, whether it's about to enter an intersection, and (if
        so) what heading it would leave that intersection with -- all
        without changing any state.

        The turn decision is made here, during planning, rather than
        later when the move is applied: right-of-way has to be judged
        against where a car is actually headed, not where it approached
        from. If the turn were decided after conflicts were resolved, a
        car simply passing straight through an intersection (compatible
        with oncoming traffic in the other lane) could turn onto the
        cross street at the last moment and genuinely cut across another
        car's path without ever having been checked against it.
        """
        rng = rng or random
        gap, oncoming = self.distance_ahead(other_cars, grid)
        target_speed = self.safe_speed(gap, oncoming)

        if target_speed > self.speed:
            speed = min(target_speed, self.speed + self.max_accel * dt)
        else:
            speed = max(target_speed, self.speed - self.max_decel * dt)

        # don't overshoot the car ahead even mid-acceleration (halved if
        # that car is oncoming -- see safe_speed's docstring for why)
        if gap is not None:
            budget = gap - self.safety_gap
            if oncoming:
                budget /= 2
            speed = min(speed, max(0.0, budget))

        dx, dy = self.direction
        step_dist = speed * dt
        new_x = self.x + dx * step_dist
        new_y = self.y + dy * step_dist

        # did this move cross (or land on) an intersection?
        if dx != 0:
            crossed = int(new_x) != int(self.x) or grid.is_intersection(new_x, self.y)
        else:
            crossed = int(new_y) != int(self.y) or grid.is_intersection(self.x, new_y)

        intersection_cell = None
        chosen_direction = self.direction
        if crossed:
            if dx != 0:
                ix = _first_boundary_crossed(self.x, new_x, dx)
                iy = self.y
            else:
                ix = self.x
                iy = _first_boundary_crossed(self.y, new_y, dy)
            if ix is not None and iy is not None:
                ix, iy = grid.wrap(ix, iy)
                if grid.is_intersection(ix, iy):
                    intersection_cell = (int(ix), int(iy))
                    reverse = (-dx, -dy)
                    # never consider reversing course at an intersection -- a
                    # real driver doesn't randomly U-turn, and on a
                    # bidirectional street a U-turn would drop this car
                    # straight into the oncoming lane it may have just been
                    # safely passing
                    options = [d for d in grid.directions_at(ix, iy) if d != reverse]
                    on_artery = grid.is_artery_travel(ix, iy, self.direction)
                    turn_prob = self.artery_turn_probability if on_artery else self.turn_probability
                    # prefer continuing straight if it's still a legal option
                    if self.direction in options and rng.random() > turn_prob:
                        chosen_direction = self.direction
                    elif options:
                        chosen_direction = rng.choice(options)

        new_x, new_y = grid.wrap(new_x, new_y)
        return Move(self, speed, new_x, new_y, intersection_cell, chosen_direction)

    def apply_move(self, move: Move, yield_right_of_way: bool = False) -> None:
        """
        Apply a previously-planned Move. If `yield_right_of_way` is True,
        this car lost the right-of-way for an intersection it planned to
        enter this tick: it brakes to a stop and holds its current
        position instead, and tries again next tick.
        """
        if yield_right_of_way:
            self.speed = 0.0
            return  # stay put; direction unchanged, will re-plan next tick

        self.speed = move.speed
        self.direction = move.chosen_direction
        self.x, self.y = move.new_x, move.new_y

    def step(
        self,
        grid,
        other_cars: List["Car"],
        dt: float = 1.0,
        rng: Optional[random.Random] = None,
    ) -> None:
        """
        Convenience wrapper: plan and immediately apply a move for this
        car alone, with no right-of-way arbitration against other cars.
        Fine for quick single-car experiments; a real multi-car
        simulation should use simulation.step_all(grid, cars, ...)
        instead, so that cars converging on the same intersection give
        way according to the "yield to the right" rule.
        """
        move = self.plan(grid, other_cars, dt, rng)
        self.apply_move(move, yield_right_of_way=False)

    def __repr__(self) -> str:
        return f"Car({self.id}, pos=({self.x:.2f},{self.y:.2f}), dir={self.direction}, speed={self.speed:.2f})"
