"""
job_info.json loading — derives the target thickness range for a scan.
"""

import json
import logging
import os
from typing import Tuple

logger = logging.getLogger(__name__)

DEFAULT_MIN_TARGET = 40
DEFAULT_MAX_TARGET = 60


def load_thickness_targets(ply_filepath: str) -> Tuple[float, float]:
    """
    Look for a `job_info.json` next to `ply_filepath` and derive
    (min_target, max_target) in mm from its target_thickness/tolerance.
    Falls back to (DEFAULT_MIN_TARGET, DEFAULT_MAX_TARGET) if the file is
    missing or malformed.
    """
    dir_path = os.path.dirname(ply_filepath)
    job_info_path = os.path.join(dir_path, "job_info.json")

    if not os.path.exists(job_info_path):
        return DEFAULT_MIN_TARGET, DEFAULT_MAX_TARGET

    try:
        with open(job_info_path, "r") as f:
            job_info = json.load(f)
        parameters = job_info.get("parameters", {})
        target_thickness = parameters.get("target_thickness", 30)
        tolerance = parameters.get("tolerance", 10)
        return target_thickness - tolerance, target_thickness + tolerance
    except (OSError, ValueError) as e:
        logger.warning("Failed to read %s: %s", job_info_path, e)
        return DEFAULT_MIN_TARGET, DEFAULT_MAX_TARGET
