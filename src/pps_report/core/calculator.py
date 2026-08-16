"""
Calculate surface area and volume from point cloud data.
Uses surface reconstruction and thickness information.
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Optional

from pps_report.core.helper import surface_area as bpa_surface_area

from pps_report.utils.utils import timeit

@dataclass
class CalculationResult:
    """Results from area and volume calculations."""
    surface_area_m2: float  # Surface area in square meters
    volume_m3: float  # Volume in cubic meters
    mean_thickness_mm: float  # Mean thickness in mm
    min_thickness_mm: float
    max_thickness_mm: float
    std_thickness_mm: float
    num_points: int
    area_reached_target_m2: float = 0

    @property
    def surface_area_cm2(self) -> float:
        return self.surface_area_m2 * 10000

    @property
    def area_reached_target(self) -> float:
        return self.area_reached_target_m2 

    @property
    def volume_liters(self) -> float:
        return self.volume_m3 * 1000
    @property
    def area_reached_target_percent(self) -> Optional[float]:
        if self.surface_area_m2 > 0:
            return 100 * self.area_reached_target_m2 / self.surface_area_m2
        return None


@dataclass
class ThicknessDistribution:
    """Thickness distribution for histogram."""
    below_target: int  # Points below target thickness
    within_target: int  # Points within target range
    above_target: int  # Points above target thickness
    
    below_target_percent: float
    within_target_percent: float
    above_target_percent: float
    
    histogram_bins: np.ndarray
    histogram_counts: np.ndarray
    
    target_min: float
    target_max: float



@timeit
def _extract_points_and_distances(cloud):
    """Extract point and thickness arrays from a cloud-like object."""
    if cloud is None:
        return np.empty((0, 3), dtype=np.float64), np.empty((0,), dtype=np.float64)

    if isinstance(cloud, tuple) and len(cloud) == 2:
        pts, dists = cloud
        #TODO: xử lý dists < -30 này là lỗi sai normal, cần xem xét lại cách tính thickness

        return np.asarray(pts, dtype=np.float64), np.asarray(dists, dtype=np.float64)

    if hasattr(cloud, 'points') and hasattr(cloud, 'distances'):
        return np.asarray(cloud.points, dtype=np.float64), np.asarray(cloud.distances, dtype=np.float64)

    raise TypeError(
        "cloud must be a tuple (points, distances) or an object with .points and .distances"
    )



@timeit
def _to_open3d_pointcloud(cloud, points=None):
    """Convert a cloud-like object into an Open3D PointCloud."""
    try:
        import open3d as o3d
    except ImportError as exc:
        raise ImportError("Open3D is required for BPA surface estimation") from exc

    if isinstance(cloud, o3d.geometry.PointCloud):
        return cloud

    if points is None and hasattr(cloud, 'points'):
        points = cloud.points

    if points is None:
        raise TypeError("Cannot convert cloud to Open3D PointCloud; no point data available")

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(np.asarray(points, dtype=np.float64))
    return pcd


@timeit
def calculate_area_and_volume(*args, method: str = "bpa", target_min=None) -> CalculationResult:
    """
    Calculate surface area and volume from a cloud-like object.

    Volume is calculated as: Surface Area × Mean Thickness

    Args:
        *args: Either (cloud,) where cloud has .points and .distances or is a
               tuple/list (points, distances), or (points, distances).
        method: Ignored. BPA is always used for surface area estimation.

    Returns:
        CalculationResult with area and volume
    """
    if len(args) == 1:
        cloud = args[0]
    elif len(args) == 2:
        cloud = (args[0], args[1])
    else:
        raise TypeError(
            "calculate_area_and_volume() takes either a single cloud object or two arguments (points, distances)."
        )

    points, distances = _extract_points_and_distances(cloud)

    if len(points) == 0:
        return CalculationResult(
            surface_area_m2=0,
            volume_m3=0,
            mean_thickness_mm=0,
            min_thickness_mm=0,
            max_thickness_mm=0,
            std_thickness_mm=0,
            num_points=0,
            area_reached_target_m2=0
        )

    distances[np.abs(distances) < 12] = 0 # set thickness < 12mm to 0, consider as no damage (tùy chỉnh ngưỡng này)
    distances[np.abs(distances) > 500] = 0 # set thickness > 500mm to 0, consider as noise

    _min_reached_thickness_mm = target_min if target_min is not None else 20
    _mask_reached_target = distances > _min_reached_thickness_mm

    _reached_points = points[_mask_reached_target]
    _reached_distances = distances[_mask_reached_target]
    if len(_reached_points) < 100:  # ngưỡng tùy chọn
        reached_area = 0.0
    else:
        reached_pcd = _to_open3d_pointcloud(None, _reached_points)
        reached_area = bpa_surface_area(reached_pcd, radii=(0.03, 0.05))  # m²

    avg_thickness_mm = _reached_distances.mean() if len(_reached_distances) > 0 else 0

    pcd = _to_open3d_pointcloud(cloud, points)
    total_area_m2 = bpa_surface_area(pcd,radii=(0.1, 0.15))
    volume_m3 = reached_area * avg_thickness_mm/1000

    return CalculationResult(
        surface_area_m2=total_area_m2,
        volume_m3=volume_m3,
        mean_thickness_mm=avg_thickness_mm,
        min_thickness_mm=float(np.min(_reached_distances)),
        max_thickness_mm=float(np.max(_reached_distances)),
        std_thickness_mm=float(np.std(_reached_distances)),
        num_points=len(points),
        area_reached_target_m2=reached_area
    )


@timeit
def calculate_thickness_distribution(distances: np.ndarray,
                                    target_min: float,
                                    target_max: float,
                                    num_bins: int = 50) -> ThicknessDistribution:
    """
    Calculate thickness distribution for histogram.
    
    Args:
        distances: Array of thickness values in mm
        target_min: Minimum target thickness (mm)
        target_max: Maximum target thickness (mm)
        num_bins: Number of histogram bins
        
    Returns:
        ThicknessDistribution with histogram data
    """
    # Filter valid values
    valid = distances[~np.isnan(distances) & ~np.isinf(distances)]
    
    if len(valid) == 0:
        return ThicknessDistribution(
            below_target=0,
            within_target=0,
            above_target=0,
            below_target_percent=0,
            within_target_percent=0,
            above_target_percent=0,
            histogram_bins=np.array([]),
            histogram_counts=np.array([]),
            target_min=target_min,
            target_max=target_max
        )
    
    # Count points in each category
    below = np.sum(valid < target_min)
    within = np.sum((valid >= target_min) & (valid <= target_max))
    above = np.sum(valid > target_max)
    
    total = len(valid)
    
    # Create histogram
    hist_min = max(0, valid.min() - 10)
    hist_max = valid.max() + 10
    bins = np.linspace(hist_min, hist_max, num_bins + 1)
    counts, _ = np.histogram(valid, bins=bins)
    
    return ThicknessDistribution(
        below_target=int(below),
        within_target=int(within),
        above_target=int(above),
        below_target_percent=100 * below / total,
        within_target_percent=100 * within / total,
        above_target_percent=100 * above / total,
        histogram_bins=bins,
        histogram_counts=counts,
        target_min=target_min,
        target_max=target_max
    )
