"""
demo.py

Small runnable example: build a grid, drop some cars on it, step the
simulation, and print an ASCII frame each tick.
"""

import argparse
import random
import time
from grid import StreetGrid
from car import Car
from visualization import render_with_legend, clear_screen
import simulation


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
        "--artery-row", type=int, default=None,
        help="street row to designate as a major artery (default: closest to the middle)",
    )
    parser.add_argument(
        "--artery-col", type=int, default=None,
        help="street col to designate as a major artery (default: closest to the middle)",
    )
    parser.add_argument(
        "--artery-fraction", type=float, default=0.6,
        help="fraction of cars that start on one of the two arteries (default: 0.6)",
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
    parser.add_argument(
        "--delay", type=float, default=0.3,
        help="seconds to pause between frames (default: 0.3)",
    )
    parser.add_argument(
        "--no-clear", action="store_true",
        help="don't wipe the screen between frames (e.g. when piping output to a file)",
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="disable VT100 color codes on car arrows (e.g. when piping output to a file)",
    )
    return parser.parse_args()


def make_demo_grid(width: int = 20, height: int = 12,
                    row_spacing: int = 3, col_spacing: int = 4,
                    artery_row: int = None, artery_col: int = None) -> StreetGrid:
    # streets every `row_spacing`/`col_spacing` rows/cols (a city-block layout)
    street_rows = list(range(0, height, row_spacing))
    street_cols = list(range(0, width, col_spacing))
    return StreetGrid(
        width, height,
        street_rows=street_rows, street_cols=street_cols,
        artery_row=artery_row, artery_col=artery_col,
    )


def _spawn_conflicts(x: float, y: float, grid: StreetGrid, cars: list, min_gap: float) -> bool:
    """True if placing a car at (x, y) would start it closer than min_gap
    to an existing car sharing its row or column (accounting for wrap)."""
    for other in cars:
        if abs(other.y - y) < 1e-6:
            gap = min(abs(other.x - x), grid.width - abs(other.x - x))
            if gap < min_gap:
                return True
        if abs(other.x - x) < 1e-6:
            gap = min(abs(other.y - y), grid.height - abs(other.y - y))
            if gap < min_gap:
                return True
    return False


def make_demo_cars(grid: StreetGrid, n: int, rng: random.Random,
                    artery_fraction: float = 0.6, min_spawn_gap: float = 1.5,
                    max_attempts: int = 50) -> list:
    cars = []
    rows = list(grid.street_rows)
    cols = list(grid.street_cols)
    for _ in range(n):
        for attempt in range(max_attempts):
            on_artery_row = grid.artery_row is not None
            on_artery_col = grid.artery_col is not None
            spawn_on_artery = rng.random() < artery_fraction and (on_artery_row or on_artery_col)

            if spawn_on_artery:
                # put this car directly on one of the two designated arteries
                if on_artery_row and (not on_artery_col or rng.random() < 0.5):
                    y = grid.artery_row
                    x = rng.uniform(0, grid.width - 1)
                    direction = rng.choice([(1, 0), (-1, 0)])
                else:
                    x = grid.artery_col
                    y = rng.uniform(0, grid.height - 1)
                    direction = rng.choice([(0, 1), (0, -1)])
            elif rng.random() < 0.5 and rows:
                y = rng.choice(rows)
                x = rng.uniform(0, grid.width - 1)
                direction = rng.choice([(1, 0), (-1, 0)])
            else:
                x = rng.choice(cols)
                y = rng.uniform(0, grid.height - 1)
                direction = rng.choice([(0, 1), (0, -1)])

            if not _spawn_conflicts(x, y, grid, cars, min_spawn_gap):
                break
            # else: try a different random spot (last attempt is used as-is)
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
        artery_row=args.artery_row,
        artery_col=args.artery_col,
    )
    cars = make_demo_cars(grid, n=args.cars, rng=rng, artery_fraction=args.artery_fraction)

    for tick in range(args.ticks):
        if not args.no_clear:
            clear_screen()
        print(render_with_legend(grid, cars, tick, color=not args.no_color))
        print()
        simulation.step_all(grid, cars, dt=1.0, rng=rng)
        if args.delay > 0:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
