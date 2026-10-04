"""
Geometric layout model shared by native-text and OCR pages.

Words carry bounding boxes (PDF points, origin top-left). Lines are rebuilt from
word geometry rather than trusting the PDF's content-stream order, which is often
wrong for tables and multi-column pages. Cells are runs of words separated by
gaps wider than a multiple of the typical inter-word space.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    conf: float | None = None  # OCR confidence 0-100; None for native text

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def height(self) -> float:
        return max(self.bottom - self.top, 0.1)


@dataclass
class Cell:
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def x1(self) -> float:
        return max(w.x1 for w in self.words)

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def conf(self) -> float | None:
        confs = [w.conf for w in self.words if w.conf is not None]
        return min(confs) if confs else None


@dataclass
class Line:
    words: list[Word]
    index: int = 0
    cells: list[Cell] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def top(self) -> float:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> float:
        return max(w.bottom for w in self.words)


def build_lines(words: list[Word]) -> list[Line]:
    """Group words into lines by vertical overlap, ordered top-to-bottom, left-to-right."""
    if not words:
        return []
    heights = [w.height for w in words]
    tol = max(median(heights) * 0.45, 1.0)
    ordered = sorted(words, key=lambda w: (w.yc, w.x0))
    groups: list[list[Word]] = []
    centers: list[float] = []
    for w in ordered:
        if groups and abs(w.yc - centers[-1]) <= tol:
            groups[-1].append(w)
            centers[-1] = sum(x.yc for x in groups[-1]) / len(groups[-1])
        else:
            groups.append([w])
            centers.append(w.yc)
    lines = [Line(sorted(g, key=lambda w: w.x0), i) for i, g in enumerate(groups)]
    gap = typical_space(words)
    for line in lines:
        line.cells = split_cells(line.words, gap)
    return lines


def typical_space(words: list[Word]) -> float:
    """Estimate the normal inter-word gap from character widths."""
    widths = [(w.x1 - w.x0) / max(len(w.text), 1) for w in words if w.text]
    char_w = median(widths) if widths else 4.0
    return max(char_w * 1.0, 1.5)


def split_cells(words: list[Word], space: float, factor: float = 2.2) -> list[Cell]:
    """Split a line's words into cells where the horizontal gap exceeds factor × space."""
    if not words:
        return []
    cells: list[Cell] = [Cell([words[0]])]
    for prev, cur in zip(words, words[1:], strict=False):
        if cur.x0 - prev.x1 > space * factor:
            cells.append(Cell([cur]))
        else:
            cells[-1].words.append(cur)
    return cells


def detect_columns(lines: list[Line], page_width: float) -> int:
    """Rough count of text columns (1 or 2) from a vertical whitespace gutter."""
    if page_width <= 0 or len(lines) < 10:
        return 1
    bins = 60
    occupancy = [0] * bins
    for line in lines:
        for w in line.words:
            a = max(0, min(bins - 1, int(w.x0 / page_width * bins)))
            b = max(0, min(bins - 1, int(w.x1 / page_width * bins)))
            for i in range(a, b + 1):
                occupancy[i] += 1
    middle = occupancy[int(bins * 0.35) : int(bins * 0.65)]
    if (
        middle
        and min(middle) <= max(occupancy) * 0.02
        and sum(occupancy[: bins // 3])
        and sum(occupancy[2 * bins // 3 :])
    ):
        return 2
    return 1
