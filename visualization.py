"""
visualization.py

ASCII rendering of a StreetGrid and the Cars currently on it.
"""

from typing import List
from car import Car, DIRECTION_ARROWS
from grid import StreetGrid

# VT100/ANSI escape codes.
# \033[H   -> move cursor to home (row 1, col 1)
# \033[2J  -> clear the whole screen
# \033[3J  -> also clear the terminal's scrollback buffer (xterm extension)
_CURSOR_HOME = "\033[H"
_CLEAR_SCREEN = "\033[2J"
_CLEAR_SCROLLBACK = "\033[3J"
_SGR_RESET = "\033[0m"
_SGR_REVERSE = "7"  # reverse video: swaps foreground/background


def clear_screen(clear_scrollback: bool = False) -> None:
    """
    Wipe the terminal and move the cursor back to the top-left, so the
    next frame is drawn in place instead of scrolling. Call this right
    before printing a new frame.
    """
    seq = _CURSOR_HOME + _CLEAR_SCREEN
    if clear_scrollback:
        seq += _CLEAR_SCROLLBACK
    print(seq, end="", flush=True)


def render(grid: StreetGrid, cars: List[Car], color: bool = True) -> str:
    """
    Build a text picture of the grid:
      '+'  intersection
      '-'  horizontal street
      '|'  vertical street
      '.'  not a street
      a direction arrow ('>','<','^','v') for a car, or '#' if more than
      one car lands on the same cell (rare, since cars keep a safe
      distance, but possible right after a turn).

    If color is True (default), each car's arrow is drawn in reverse
    video using car.color as the SGR color code, so the car shows up as
    a solid block of its color (foreground/background swapped) rather
    than just a colored character; set color=False for plain text, e.g.
    when writing to a file/log.
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
            car = cars_here[0]
            glyph = DIRECTION_ARROWS.get(car.direction, "*")
            if color:
                glyph = f"\033[{_SGR_REVERSE};{car.color}m{glyph}{_SGR_RESET}"
            canvas[cy][cx] = glyph
        else:
            glyph = "#"
            if color:
                glyph = f"\033[{_SGR_REVERSE};1m{glyph}{_SGR_RESET}"  # reverse + bold, no specific car color
            canvas[cy][cx] = glyph

    lines = ["".join(row) for row in canvas]
    return "\n".join(lines)


def render_with_legend(grid: StreetGrid, cars: List[Car], tick: int = None, color: bool = True) -> str:
    header = f"tick {tick}\n" if tick is not None else ""
    body = render(grid, cars, color=color)
    legend = (
        "\nlegend: + intersection  - / | street  = / I major artery  "
        ". no street  > < ^ v car heading (each car in reverse-video color)  "
        "# multiple cars"
    )
    return header + body + legend
