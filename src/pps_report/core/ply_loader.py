"""
PLY file loader with support for custom scalar fields (distances).

Uses Open3D's tensor-based PLY reader (MIT licensed) instead of the
`plyfile` package (GPL-3.0-or-later), which is unsuitable for a
closed-source/commercial distribution.
"""

import logging
import numpy as np
import open3d as o3d
from dataclasses import dataclass
from typing import Optional, List, Tuple
import os

logger = logging.getLogger(__name__)


@dataclass
class PointCloudData:
    """Point cloud data structure."""
    points: np.ndarray  # (N, 3) array of XYZ coordinates
    distances: np.ndarray  # (N,) array of distance/thickness values in mm
    colors: Optional[np.ndarray] = None  # (N, 3) array of RGB colors
    normals: Optional[np.ndarray] = None  # (N, 3) array of normal vectors

    @property
    def num_points(self) -> int:
        return len(self.points)

    @property
    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return (min_xyz, max_xyz) bounds."""
        return self.points.min(axis=0), self.points.max(axis=0)

    @property
    def center(self) -> np.ndarray:
        """Return center point of the cloud."""
        return self.points.mean(axis=0)

    def get_thickness_stats(self) -> dict:
        """Get statistics about thickness/distance values."""
        valid_distances = self.distances[~np.isnan(self.distances)]
        if len(valid_distances) == 0:
            return {
                'min': 0, 'max': 0, 'mean': 0, 'std': 0, 'median': 0
            }
        return {
            'min': float(np.min(valid_distances)),
            'max': float(np.max(valid_distances)),
            'mean': float(np.mean(valid_distances)),
            'std': float(np.std(valid_distances)),
            'median': float(np.median(valid_distances))
        }


_DISTANCE_FIELD_CANDIDATES = [
    'distances',
    'distance',
    'thickness',
    'scalar_distances',
    'scalar_Distances',
    'Distances',
    'C2C_absolute_distances',
    'C2C_signed_distances',
]


def load_ply(filepath: str, distance_field: str = "distances") -> PointCloudData:
    """
    Load a PLY file with custom distance/thickness field.

    Args:
        filepath: Path to PLY file
        distance_field: Name of the scalar field containing thickness data

    Returns:
        PointCloudData object
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"PLY file not found: {filepath}")

    pcd = o3d.t.io.read_point_cloud(filepath)
    point = pcd.point

    if "positions" not in point:
        raise ValueError(f"PLY file has no vertex positions: {filepath}")
    points = point["positions"].numpy().astype(np.float64)

    # Try the requested field first, then the usual fallback names
    distances = None
    for name in [distance_field, *_DISTANCE_FIELD_CANDIDATES]:
        if name in point:
            distances = point[name].numpy().reshape(-1).astype(np.float64)
            mask = (distances > -25) & (distances < 25)
            distances[mask] = np.abs(distances[mask])
            distances = np.where(distances < -25, np.abs(distances), distances)
            logger.info("Found distance field: '%s'", name)
            break

    if distances is None:
        available_fields = get_ply_fields(filepath)
        logger.warning("Distance field not found. Available fields: %s", available_fields)
        distances = np.zeros(len(points))

    colors = None
    if "colors" in point:
        colors = point["colors"].numpy().astype(np.float64)
        if colors.max() > 1:
            colors = colors / 255.0

    normals = None
    if "normals" in point:
        normals = point["normals"].numpy().astype(np.float64)

    return PointCloudData(
        points=points,
        distances=distances,
        colors=colors,
        normals=normals
    )


def get_ply_fields(filepath: str) -> List[str]:
    """Get list of all per-vertex scalar fields in a PLY file."""
    pcd = o3d.t.io.read_point_cloud(filepath)
    return [name for name in dir(pcd.point) if not name.startswith("_")]


def filter_by_distance(cloud: PointCloudData,
                       min_dist: float = None,
                       max_dist: float = None) -> PointCloudData:
    """
    Filter point cloud by distance values.

    Args:
        cloud: Input point cloud
        min_dist: Minimum distance threshold (mm)
        max_dist: Maximum distance threshold (mm)

    Returns:
        Filtered PointCloudData
    """
    mask = np.ones(cloud.num_points, dtype=bool)

    if min_dist is not None:
        mask &= cloud.distances >= min_dist
    if max_dist is not None:
        mask &= cloud.distances <= max_dist

    return PointCloudData(
        points=cloud.points[mask],
        distances=cloud.distances[mask],
        colors=cloud.colors[mask] if cloud.colors is not None else None,
        normals=cloud.normals[mask] if cloud.normals is not None else None
    )
