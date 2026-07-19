"""
grid.py

Defines the StreetGrid: a Manhattan-style lattice of streets a car agent
is allowed to travel on. A subset of rows and a subset of columns are
designated as streets. A cell (x, y) is "on the street network" if x is
an integer street-column, or y is an integer street-row (or both, which
makes it an intersection).

Coordinates are floats internally (so cars can be *between* integer grid
points while driving), but streets themselves live on integer lines.
"""

from typing import Iterable, Optional, Set, Tuple, List


class StreetGrid:
    def __init__(
        self,
        width: int,
        height: int,
        street_rows: Optional[Iterable[int]] = None,
        street_cols: Optional[Iterable[int]] = None,
    ):
        """
        width, height: size of the grid (x in [0, width-1], y in [0, height-1])
        street_rows: which y-values are horizontal streets (default: every row)
        street_cols: which x-values are vertical streets (default: every col)
        """
        if width < 1 or height < 1:
            raise ValueError("width and height must be positive")

        self.width = width
        self.height = height

        self.street_rows: Set[int] = (
            set(range(height)) if street_rows is None else set(street_rows)
        )
        self.street_cols: Set[int] = (
            set(range(width)) if street_cols is None else set(street_cols)
        )

        for r in self.street_rows:
            if not (0 <= r < height):
                raise ValueError(f"street row {r} out of bounds")
        for c in self.street_cols:
            if not (0 <= c < width):
                raise ValueError(f"street col {c} out of bounds")

        if not self.street_rows and not self.street_cols:
            raise ValueError("grid needs at least one street row or column")

    # -- geometry helpers ---------------------------------------------

    @staticmethod
    def _is_int(v: float, tol: float = 1e-6) -> bool:
        return abs(v - round(v)) < tol

    def is_on_row_street(self, y: float) -> bool:
        return self._is_int(y) and int(round(y)) in self.street_rows

    def is_on_col_street(self, x: float) -> bool:
        return self._is_int(x) and int(round(x)) in self.street_cols

    def is_street(self, x: float, y: float) -> bool:
        """True if (x, y) lies on some street (row or column)."""
        return self.is_on_row_street(y) or self.is_on_col_street(x)

    def is_intersection(self, x: float, y: float) -> bool:
        """True if (x, y) is where a street row and street column cross."""
        return self.is_on_row_street(y) and self.is_on_col_street(x)

    def directions_at(self, x: float, y: float) -> List[Tuple[int, int]]:
        """
        Which travel directions are legal to be moving in while sitting at
        (x, y)? At an intersection that's up/down/left/right; on a plain
        stretch of horizontal street just left/right, etc.
        """
        dirs = []
        if self.is_on_row_street(y):
            dirs += [(1, 0), (-1, 0)]
        if self.is_on_col_street(x):
            dirs += [(0, 1), (0, -1)]
        return dirs

    def wrap(self, x: float, y: float) -> Tuple[float, float]:
        """Toroidal wrap so cars leaving one edge re-enter the opposite edge."""
        return x % self.width, y % self.height

    # -- convenience for building/inspecting the grid -------------------

    def cell_char(self, x: int, y: int) -> str:
        """Background character for an empty grid cell (no car on it)."""
        on_row = y in self.street_rows
        on_col = x in self.street_cols
        if on_row and on_col:
            return "+"
        if on_row:
            return "-"
        if on_col:
            return "|"
        return "."
