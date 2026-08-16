"""
Project persistence — saves/restores segments (and their annotations) as a
sidecar file next to the source PLY, so reopening the same PLY can restore
previously-created segments.
"""

import json
import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

PROJECT_SUFFIX = ".ppsproj.npz"


def project_path_for(ply_filepath: str) -> str:
    base, _ = os.path.splitext(ply_filepath)
    return base + PROJECT_SUFFIX


def _strip_actor(annotation: dict) -> dict:
    return {k: v for k, v in annotation.items() if k != "actor"}


def save_project(ply_filepath: str, layer_manager, target_min: float, target_max: float) -> str:
    """Save all non-original layers (segments) + their annotations to a sidecar file."""
    segments = [layer for layer in layer_manager.layers if not layer.is_original]

    meta = {
        "target_min": target_min,
        "target_max": target_max,
        "segments": [
            {
                "name": seg.name,
                "color": list(seg.color) if seg.color is not None else None,
                "visible": seg.visible,
                "annotations": [_strip_actor(ann) for ann in seg.annotations],
            }
            for seg in segments
        ],
    }

    arrays = {"_meta": np.array(json.dumps(meta))}
    for i, seg in enumerate(segments):
        arrays[f"points_{i}"] = seg.points
        arrays[f"distances_{i}"] = seg.distances

    path = project_path_for(ply_filepath)
    np.savez_compressed(path, **arrays)
    logger.info("Saved project (%d segment(s)) to %s", len(segments), path)
    return path


def load_project(ply_filepath: str) -> Optional[dict]:
    """Load a previously-saved project sidecar for this PLY, if one exists."""
    path = project_path_for(ply_filepath)
    if not os.path.exists(path):
        return None

    with np.load(path, allow_pickle=False) as data:
        meta = json.loads(str(data["_meta"]))
        segments = []
        for i, seg_meta in enumerate(meta["segments"]):
            segments.append({
                "name": seg_meta["name"],
                "points": data[f"points_{i}"],
                "distances": data[f"distances_{i}"],
                "color": tuple(seg_meta["color"]) if seg_meta["color"] is not None else None,
                "visible": seg_meta["visible"],
                "annotations": seg_meta["annotations"],
            })

    return {
        "target_min": meta.get("target_min"),
        "target_max": meta.get("target_max"),
        "segments": segments,
    }
