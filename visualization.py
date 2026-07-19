"""
visualization.py

ASCII rendering of a StreetGrid and the Cars currently on it.
"""

from typing import List
from car import Car, DIRECTION_ARROWS
from grid import StreetGrid


def render(grid: StreetGrid, cars: List[Car]) -> str:
    """
    Build a text picture of the grid:
      '+'  intersection
      '-'  horizontal street
      '|'  vertical street
      '.'  not a street
      a direction arrow ('>','<','^','v') for a car, or a digit/letter
      if more than one car lands on the same cell (rare, since cars keep
      a safe distance, but possible right after a turn).
    """
    canvas = [
        [grid.cell_char(x, y) for x in range(grid.width)]
        for y in range(grid.height)
    ]

    occupied = {}
    for car in cars:
        cx, cy = int(round(car.x)) % grid.width, int(round(car.y)) % grid.height
        occupied.setdefault((cx, cy), []).append(car)

    for (cx, cy), cars_here in occupied.items():
        if len(cars_here) == 1:
            canvas[cy][cx] = DIRECTION_ARROWS.get(cars_here[0].direction, "*")
        else:
            canvas[cy][cx] = "#"  # more than one car on this cell

    lines = ["".join(row) for row in canvas]
    return "\n".join(lines)


def render_with_legend(grid: StreetGrid, cars: List[Car], tick: int = None) -> str:
    header = f"tick {tick}\n" if tick is not None else ""
    body = render(grid, cars)
    legend = (
        "\nlegend: + intersection  - / | street  . no street  "
        "> < ^ v car heading  # multiple cars"
    )
    return header + body + legend
