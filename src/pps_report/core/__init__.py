"""
Core modules for tunnel analysis.
"""

from .ply_loader import load_ply, PointCloudData, get_ply_fields, filter_by_distance
from .filename_parser import parse_filename, ProjectInfo
from .calculator import (
    calculate_area_and_volume, 
    calculate_thickness_distribution,
    CalculationResult,
    ThicknessDistribution
)
from .segmentation import SegmentationState, Segment, SelectionMode
from .layer_manager import Layer, LayerManager
from .job_info import load_thickness_targets
from .project_io import save_project, load_project, project_path_for

__all__ = [
    'load_ply',
    'PointCloudData',
    'get_ply_fields',
    'filter_by_distance',
    'parse_filename',
    'ProjectInfo',
    'calculate_area_and_volume',
    'calculate_thickness_distribution',
    'CalculationResult',
    'ThicknessDistribution',
    'SegmentationState',
    'Segment',
    'SelectionMode',
    'Layer',
    'LayerManager',
    'load_thickness_targets',
    'save_project',
    'load_project',
    'project_path_for',
]
