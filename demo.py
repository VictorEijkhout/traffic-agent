"""
demo.py

Small runnable example: build a grid, drop some cars on it, step the
simulation, and print an ASCII frame each tick.
"""

import argparse
import random
from grid import StreetGrid
from car import Car
from visualization import render_with_legend


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a small ASCII traffic simulation on a street grid."
    )
    parser.add_argument(
        "--gridx", type=int, default=20,
        help="grid width, i.e. number of columns (default: 20)",
    )
    parser.add_argument(
        "--gridy", type=int, default=12,
        help="grid height, i.e. number of rows (default: 12)",
    )
    parser.add_argument(
        "--row-spacing", type=int, default=3,
        help="every Nth row is a street (default: 3)",
    )
    parser.add_argument(
        "--col-spacing", type=int, default=4,
        help="every Nth column is a street (default: 4)",
    )
    parser.add_argument(
        "--cars", type=int, default=8,
        help="number of cars to simulate (default: 8)",
    )
    parser.add_argument(
        "--ticks", type=int, default=6,
        help="number of simulation steps to run and print (default: 6)",
    )
    parser.add_argument(
        "--seed", type=int, default=7,
        help="random seed, for reproducible runs (default: 7)",
    )
    return parser.parse_args()


def make_demo_grid(width: int = 20, height: int = 12,
                    row_spacing: int = 3, col_spacing: int = 4) -> StreetGrid:
    # streets every `row_spacing`/`col_spacing` rows/cols (a city-block layout)
    street_rows = list(range(0, height, row_spacing))
    street_cols = list(range(0, width, col_spacing))
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
    args = parse_args()
    rng = random.Random(args.seed)
    grid = make_demo_grid(
        width=args.gridx,
        height=args.gridy,
        row_spacing=args.row_spacing,
        col_spacing=args.col_spacing,
    )
    cars = make_demo_cars(grid, n=args.cars, rng=rng)

    for tick in range(args.ticks):
        print(render_with_legend(grid, cars, tick))
        print()
        for car in cars:
            car.step(grid, cars, dt=1.0, rng=rng)


if __name__ == "__main__":
    main()
