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
"""

import random
from typing import List, Optional, Tuple

Direction = Tuple[int, int]  # one of (1,0), (-1,0), (0,1), (0,-1)

DIRECTION_ARROWS = {
    (1, 0): ">",
    (-1, 0): "<",
    (0, 1): "v",
    (0, -1): "^",
}


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

        self.id = car_id or f"C{Car._next_id}"
        Car._next_id += 1

    # -- geometry --------------------------------------------------

    @property
    def position(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def _same_lane(self, other: "Car") -> bool:
        """
        Two cars are in the same lane if they're moving along the same
        street line in the same direction (so 'ahead' is well-defined):
        same row & same horizontal heading, or same column & same
        vertical heading.
        """
        if self.direction != other.direction:
            return False
        if self.direction[0] != 0:  # moving horizontally -> compare row
            return abs(self.y - other.y) < 1e-6
        else:  # moving vertically -> compare column
            return abs(self.x - other.x) < 1e-6

    def distance_ahead(self, other_cars: List["Car"], grid_width: int, grid_height: int) -> Optional[float]:
        """
        Distance (along the direction of travel) to the nearest car ahead
        of this one in the same lane, accounting for toroidal wraparound.
        Returns None if there's no car ahead to worry about.
        """
        best = None
        dx, dy = self.direction
        span = grid_width if dx != 0 else grid_height
        my_pos = self.x if dx != 0 else self.y

        for other in other_cars:
            if other is self or not self._same_lane(other):
                continue
            other_pos = other.x if dx != 0 else other.y
            # signed forward distance, wrapped to [0, span)
            forward = (other_pos - my_pos) * (dx + dy)  # dx or dy is the +-1 component
            forward %= span
            if forward <= 1e-9:
                continue  # same spot or "behind" after wrap -> ignore
            if best is None or forward < best:
                best = forward
        return best

    # -- safe-distance / car-following rule -------------------------

    def safe_speed(self, gap: Optional[float]) -> float:
        """
        The speed this car *should* be going given the gap to the car
        ahead (None = no car ahead / open road).
        """
        if gap is None:
            return self.max_speed
        desired = gap - self.safety_gap
        return max(0.0, min(self.max_speed, desired))

    def step(
        self,
        grid,
        other_cars: List["Car"],
        dt: float = 1.0,
        rng: Optional[random.Random] = None,
    ) -> None:
        """
        Advance this car by one simulation tick:
          1. look at the gap to the car ahead and compute a safe target speed
          2. ease actual speed toward that target (bounded accel/decel)
          3. move forward; if that puts us on/through an intersection,
             optionally pick a new legal direction there
          4. wrap around grid edges
        """
        rng = rng or random

        gap = self.distance_ahead(other_cars, grid.width, grid.height)
        target_speed = self.safe_speed(gap)

        if target_speed > self.speed:
            self.speed = min(target_speed, self.speed + self.max_accel * dt)
        else:
            self.speed = max(target_speed, self.speed - self.max_decel * dt)

        # don't overshoot the car ahead even mid-acceleration
        if gap is not None:
            self.speed = min(self.speed, max(0.0, gap - self.safety_gap))

        dx, dy = self.direction
        step_dist = self.speed * dt
        new_x = self.x + dx * step_dist
        new_y = self.y + dy * step_dist

        # did we cross (or land on) an intersection? snap & maybe turn.
        if dx != 0:
            crossed = int(new_x) != int(self.x) or grid.is_intersection(new_x, self.y)
        else:
            crossed = int(new_y) != int(self.y) or grid.is_intersection(self.x, new_y)

        if crossed:
            # snap to the nearest intersection point on our path, choose there
            ix = round(new_x) if dx != 0 else self.x
            iy = round(new_y) if dy != 0 else self.y
            ix, iy = grid.wrap(ix, iy)
            if grid.is_intersection(ix, iy):
                options = grid.directions_at(ix, iy)
                # prefer continuing straight if it's still a legal option
                if self.direction in options and rng.random() > 0.35:
                    pass  # keep going straight most of the time
                elif options:
                    self.direction = rng.choice(options)

        self.x, self.y = grid.wrap(new_x, new_y)

    def __repr__(self) -> str:
        return f"Car({self.id}, pos=({self.x:.2f},{self.y:.2f}), dir={self.direction}, speed={self.speed:.2f})"
