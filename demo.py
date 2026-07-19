"""
demo.py

Small runnable example: build a grid, drop some cars on it, step the
simulation, and print an ASCII frame each tick.
"""

import random
from grid import StreetGrid
from car import Car
from visualization import render_with_legend


def make_demo_grid() -> StreetGrid:
    # 20x12 grid, streets every 3 rows/cols (a sparser city-block layout)
    width, height = 20, 12
    street_rows = list(range(0, height, 3))
    street_cols = list(range(0, width, 4))
    return StreetGrid(width, height, street_rows=street_rows, street_cols=street_cols)


def make_demo_cars(grid: StreetGrid, n: int, rng: random.Random) -> list:
    cars = []
    rows = list(grid.street_rows)
    cols = list(grid.street_cols)
    for _ in range(n):
        if rng.random() < 0.5 and rows:
            y = rng.choice(rows)
            x = rng.uniform(0, grid.width - 1)
            direction = rng.choice([(1, 0), (-1, 0)])
        else:
            x = rng.choice(cols)
            y = rng.uniform(0, grid.height - 1)
            direction = rng.choice([(0, 1), (0, -1)])
        cars.append(
            Car(
                x=x,
                y=y,
                direction=direction,
                max_speed=rng.uniform(0.8, 1.6),
                safety_gap=1.5,
            )
        )
    return cars


def main():
    rng = random.Random(7)
    grid = make_demo_grid()
    cars = make_demo_cars(grid, n=8, rng=rng)

    for tick in range(6):
        print(render_with_legend(grid, cars, tick))
        print()
        for car in cars:
            car.step(grid, cars, dt=1.0, rng=rng)


if __name__ == "__main__":
    main()
