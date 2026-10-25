from __future__ import annotations

import math
from dataclasses import dataclass

from cns_atlas.cells import CellView, Point

PROBE = 10.0
TILT = 4.0


@dataclass(frozen=True)
class PlacedCell:
    cell: str
    reconstruction: int
    x: float
    y: float
    angle: float
    scale: float
    mirrored: bool
    layer: str = ""
    towards: str = ""


def _lengths(points) -> list[float]:
    total, lengths = 0.0, [0.0]
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        total += math.hypot(bx - ax, by - ay)
        lengths.append(total)
    return lengths


def _segment(points, fraction: float) -> tuple[int, float]:
    lengths = _lengths(points)
    target = min(max(fraction, 0.0), 1.0) * lengths[-1]
    for i in range(1, len(points)):
        if lengths[i] >= target:
            span = lengths[i] - lengths[i - 1]
            return i, 0.0 if span == 0 else (target - lengths[i - 1]) / span
    return len(points) - 1, 1.0


def point_along(points, fraction: float) -> Point:
    i, t = _segment(points, fraction)
    (ax, ay), (bx, by) = points[i - 1], points[i]
    return ax + (bx - ax) * t, ay + (by - ay) * t


def normal_at(points, fraction: float) -> Point:
    i, _ = _segment(points, fraction)
    (ax, ay), (bx, by) = points[i - 1], points[i]
    length = math.hypot(bx - ax, by - ay) or 1.0
    return -(by - ay) / length, (bx - ax) / length


def _distance(points, p: Point) -> float:
    best = math.inf
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        dx, dy = bx - ax, by - ay
        span = dx * dx + dy * dy
        t = 0.0 if span == 0 else min(max(((p[0] - ax) * dx + (p[1] - ay) * dy) / span, 0.0), 1.0)
        best = min(best, math.hypot(ax + t * dx - p[0], ay + t * dy - p[1]))
    return best


def place_cells(view: CellView, level: str) -> tuple[PlacedCell, ...]:
    layers = {layer.key: layer.points for layer in view.layers}
    placed = []
    for cell in view.cells_at(level):
        copy = 0
        for placement in cell.placements:
            curve, target = layers[placement.layer], layers[placement.towards]
            for i in range(placement.copies):
                fraction = placement.start + (placement.end - placement.start) * (
                    (i + 0.5) / placement.copies)
                x, y = point_along(curve, fraction)
                nx, ny = normal_at(curve, fraction)
                if _distance(target, (x - nx * PROBE, y - ny * PROBE)) < _distance(
                        target, (x + nx * PROBE, y + ny * PROBE)):
                    nx, ny = -nx, -ny
                angle = math.degrees(math.atan2(ny, nx)) + ((copy % 3) - 1) * TILT
                placed.append(PlacedCell(cell.key, copy % len(cell.reconstructions), x, y, angle,
                                         cell.height, copy % 2 == 1, placement.layer,
                                         placement.towards))
                copy += 1
    return tuple(placed)


def to_frame(placed: PlacedCell, point: tuple[float, float]) -> Point:
    ux, uy = math.cos(math.radians(placed.angle)), math.sin(math.radians(placed.angle))
    sx, sy = (uy, -ux) if not placed.mirrored else (-uy, ux)
    px, py = point
    return (placed.x + (sx * px + ux * py) * placed.scale,
            placed.y + (sy * px + uy * py) * placed.scale)
