"""
Layer model for point cloud management.
Each layer (original cloud or extracted segment) is an independent entity
with its own copy of points and distance data.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import numpy as np


# Distinct colors for segments
SEGMENT_COLORS: List[Tuple[float, float, float]] = [
    (0.95, 0.25, 0.25),   # red
    (0.25, 0.85, 0.25),   # green
    (0.25, 0.50, 1.00),   # blue
    (1.00, 0.75, 0.20),   # yellow
    (0.85, 0.25, 1.00),   # purple
    (0.20, 0.90, 0.90),   # cyan
    (1.00, 0.50, 0.10),   # orange
    (0.60, 0.20, 0.80),   # violet
]


@dataclass
class Layer:
    """
    An independent point cloud layer.

    Attributes
    ----------
    name         : display name
    points       : (N, 3) XYZ coordinates
    distances    : (N,)   thickness in mm
    visible      : whether to show in 3D view and include in calculations
    is_original  : True for the PLY file loaded from disk
    color        : None  → use colormap (original only)
                   tuple → solid RGB color in [0, 1] (segments)
    """
    name: str
    points: np.ndarray
    distances: np.ndarray
    visible: bool = True
    is_original: bool = False
    color: Optional[Tuple[float, float, float]] = None
    annotations: List[Dict[str, object]] = field(default_factory=list)

    @property
    def num_points(self) -> int:
        return len(self.points)

    def get_stats(self) -> dict:
        valid = self.distances[
            ~np.isnan(self.distances) & ~np.isinf(self.distances)
        ]
        if len(valid) == 0:
            return {'min': 0, 'max': 0, 'mean': 0, 'std': 0, 'median': 0}
        return {
            'min':    float(np.min(valid)),
            'max':    float(np.max(valid)),
            'mean':   float(np.mean(valid)),
            'std':    float(np.std(valid)),
            'median': float(np.median(valid)),
        }


class LayerManager:
    """
    Manages a list of Layer objects (one original + N segments).
    The original layer is always at index 0 when present.
    """

    def __init__(self):
        self._layers: List[Layer] = []
        self._seg_count: int = 0

    # ------------------------------------------------------------------ add / remove
    def set_original(self, name: str,
                     points: np.ndarray,
                     distances: np.ndarray) -> Layer:
        """Replace the original layer (only one allowed)."""
        self._layers = [l for l in self._layers if not l.is_original]
        layer = Layer(name=name, points=points, distances=distances,
                      visible=True, is_original=True, color=None)
        self._layers.insert(0, layer)
        return layer

    def add_segment(self,
                    points: np.ndarray,
                    distances: np.ndarray,
                    name: Optional[str] = None,
                    color: Optional[Tuple[float, float, float]] = None,
                    visible: bool = True,
                    annotations: Optional[List[Dict[str, object]]] = None) -> Layer:
        """Create a new independent segment layer.

        `name`/`color`/`visible`/`annotations` may be supplied explicitly to
        restore a previously-saved segment; otherwise a name/color are
        auto-generated as usual.
        """
        self._seg_count += 1
        if name is None:
            name = f"Segment_{self._seg_count}"
        if color is None:
            color = SEGMENT_COLORS[(self._seg_count - 1) % len(SEGMENT_COLORS)]
        layer = Layer(name=name, points=points, distances=distances,
                      visible=visible, is_original=False, color=color,
                      annotations=annotations if annotations is not None else [])
        self._layers.append(layer)
        return layer

    def remove(self, name: str) -> bool:
        prev = len(self._layers)
        self._layers = [l for l in self._layers if l.name != name]
        return len(self._layers) < prev

    def rename(self, old_name: str, new_name: str) -> bool:
        layer = self.get(old_name)
        if layer is None:
            return False
        layer.name = new_name
        return True

    # ------------------------------------------------------------------ query
    def get(self, name: str) -> Optional[Layer]:
        for l in self._layers:
            if l.name == name:
                return l
        return None

    @property
    def original(self) -> Optional[Layer]:
        for l in self._layers:
            if l.is_original:
                return l
        return None

    @property
    def layers(self) -> List[Layer]:
        return list(self._layers)

    def visible_layers(self) -> List[Layer]:
        return [l for l in self._layers if l.visible]

    def combined_visible(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Concatenate points + distances of all VISIBLE layers.
        Returns empty arrays if nothing is visible.
        """
        vis = self.visible_layers()
        if not vis:
            return np.empty((0, 3), dtype=np.float64), np.empty(0, dtype=np.float64)
        pts   = np.concatenate([l.points    for l in vis])
        dists = np.concatenate([l.distances for l in vis])
        return pts, dists

    def clear(self):
        self._layers.clear()
        self._seg_count = 0

    def next_segment_name(self) -> str:
        """Preview the name the next add_segment() call would auto-generate."""
        return f"Segment_{self._seg_count + 1}"

    def clear_segments(self):
        """Remove all non-original layers (segments), keeping the original if present."""
        self._layers = [l for l in self._layers if l.is_original]
        self._seg_count = 0
