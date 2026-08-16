"""
Point cloud segmentation tools.
Supports manual selection (polygon, box, sphere) similar to CloudCompare.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum


class SelectionMode(Enum):
    """Selection mode for segmentation."""
    POLYGON = "polygon"  # 2D polygon selection (projected)
    BOX = "box"  # 3D bounding box
    SPHERE = "sphere"  # Spherical selection
    LASSO = "lasso"  # Freehand lasso


@dataclass
class Segment:
    """A segment of the point cloud."""
    name: str
    indices: np.ndarray  # Indices of points in this segment
    color: Tuple[float, float, float] = (1.0, 0.0, 0.0)  # RGB color for visualization
    visible: bool = True
    
    @property
    def num_points(self) -> int:
        return len(self.indices)


@dataclass
class SegmentationState:
    """State manager for segmentation operations."""
    segments: List[Segment] = field(default_factory=list)
    current_selection: Optional[np.ndarray] = None
    selection_mode: SelectionMode = SelectionMode.POLYGON
    
    def add_segment(self, name: str, indices: np.ndarray, 
                   color: Tuple[float, float, float] = None) -> Segment:
        """Add a new segment."""
        if color is None:
            # Generate a unique color
            color = self._generate_color(len(self.segments))
        
        segment = Segment(name=name, indices=indices, color=color)
        self.segments.append(segment)
        return segment
    
    def remove_segment(self, index: int) -> None:
        """Remove a segment by index."""
        if 0 <= index < len(self.segments):
            del self.segments[index]
    
    def get_segment_by_name(self, name: str) -> Optional[Segment]:
        """Find segment by name."""
        for seg in self.segments:
            if seg.name == name:
                return seg
        return None
    
    def get_all_selected_indices(self) -> np.ndarray:
        """Get all indices from all segments."""
        if not self.segments:
            return np.array([], dtype=int)
        return np.unique(np.concatenate([s.indices for s in self.segments]))
    
    def _generate_color(self, index: int) -> Tuple[float, float, float]:
        """Generate a unique color for segment visualization."""
        colors = [
            (1.0, 0.2, 0.2),  # Red
            (0.2, 1.0, 0.2),  # Green
            (0.2, 0.2, 1.0),  # Blue
            (1.0, 1.0, 0.2),  # Yellow
            (1.0, 0.2, 1.0),  # Magenta
            (0.2, 1.0, 1.0),  # Cyan
            (1.0, 0.6, 0.2),  # Orange
            (0.6, 0.2, 1.0),  # Purple
        ]
        return colors[index % len(colors)]


def select_by_polygon(points: np.ndarray, 
                      polygon_2d: np.ndarray,
                      camera_position: np.ndarray,
                      view_direction: np.ndarray) -> np.ndarray:
    """
    Select points inside a 2D polygon (screen space).
    
    Args:
        points: (N, 3) array of 3D points
        polygon_2d: (M, 2) array of 2D polygon vertices
        camera_position: Camera position in 3D
        view_direction: Camera view direction
        
    Returns:
        Indices of selected points
    """
    # Project 3D points to 2D screen space
    # This is a simplified projection - actual implementation depends on camera setup
    
    # Get view plane basis vectors
    up = np.array([0, 0, 1])
    right = np.cross(view_direction, up)
    right = right / np.linalg.norm(right)
    up = np.cross(right, view_direction)
    up = up / np.linalg.norm(up)
    
    # Project points onto view plane
    relative = points - camera_position
    x_proj = np.dot(relative, right)
    y_proj = np.dot(relative, up)
    projected = np.column_stack((x_proj, y_proj))
    
    # Check which points are inside polygon
    from matplotlib.path import Path
    polygon_path = Path(polygon_2d)
    inside = polygon_path.contains_points(projected)
    
    return np.where(inside)[0]


def select_by_box(points: np.ndarray,
                  box_min: np.ndarray,
                  box_max: np.ndarray) -> np.ndarray:
    """
    Select points inside a 3D bounding box.
    
    Args:
        points: (N, 3) array of 3D points
        box_min: Minimum corner of box (x, y, z)
        box_max: Maximum corner of box (x, y, z)
        
    Returns:
        Indices of selected points
    """
    inside = np.all((points >= box_min) & (points <= box_max), axis=1)
    return np.where(inside)[0]


def select_by_sphere(points: np.ndarray,
                     center: np.ndarray,
                     radius: float) -> np.ndarray:
    """
    Select points inside a sphere.
    
    Args:
        points: (N, 3) array of 3D points
        center: Center of sphere (x, y, z)
        radius: Radius of sphere
        
    Returns:
        Indices of selected points
    """
    distances = np.linalg.norm(points - center, axis=1)
    return np.where(distances <= radius)[0]


def select_by_distance_range(points: np.ndarray,
                             distances: np.ndarray,
                             min_distance: float,
                             max_distance: float) -> np.ndarray:
    """
    Select points within a distance/thickness range.
    
    Args:
        points: (N, 3) array of 3D points
        distances: (N,) array of distance values
        min_distance: Minimum distance threshold
        max_distance: Maximum distance threshold
        
    Returns:
        Indices of selected points
    """
    inside = (distances >= min_distance) & (distances <= max_distance)
    return np.where(inside)[0]


def select_by_click_region(points: np.ndarray,
                           click_point: np.ndarray,
                           radius: float,
                           camera_position: np.ndarray) -> np.ndarray:
    """
    Select points near a clicked point (for interactive picking).
    
    Args:
        points: (N, 3) array of 3D points
        click_point: 3D point where user clicked
        radius: Selection radius
        camera_position: Camera position for depth calculation
        
    Returns:
        Indices of selected points
    """
    distances = np.linalg.norm(points - click_point, axis=1)
    return np.where(distances <= radius)[0]


def grow_selection(points: np.ndarray,
                   current_indices: np.ndarray,
                   growth_distance: float) -> np.ndarray:
    """
    Grow the current selection by including nearby points.
    
    Args:
        points: (N, 3) array of all points
        current_indices: Currently selected point indices
        growth_distance: Maximum distance to grow selection
        
    Returns:
        Extended selection indices
    """
    if len(current_indices) == 0:
        return current_indices
    
    from scipy.spatial import cKDTree
    
    tree = cKDTree(points)
    selected_points = points[current_indices]
    
    # Find all points within growth distance of any selected point
    new_indices = set(current_indices)
    
    for point in selected_points:
        neighbors = tree.query_ball_point(point, growth_distance)
        new_indices.update(neighbors)
    
    return np.array(list(new_indices), dtype=int)


def invert_selection(total_points: int,
                    current_indices: np.ndarray) -> np.ndarray:
    """
    Invert the current selection.
    
    Args:
        total_points: Total number of points
        current_indices: Currently selected indices
        
    Returns:
        Inverted selection indices
    """
    all_indices = set(range(total_points))
    selected = set(current_indices)
    inverted = all_indices - selected
    return np.array(list(inverted), dtype=int)
