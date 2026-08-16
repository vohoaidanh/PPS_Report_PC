"""
Background QThread workers used by the main window.
"""

import logging

from PySide6.QtCore import QThread, Signal

from pps_report.core.calculator import (
    calculate_area_and_volume,
    calculate_thickness_distribution,
)

logger = logging.getLogger(__name__)


class CalculationWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)
    progress = Signal(int)

    def __init__(self, points, distances, target_min, target_max):
        super().__init__()
        self.points = points
        self.distances = distances
        self.target_min = target_min
        self.target_max = target_max

    def run(self):
        try:
            self.progress.emit(10)
            calc = calculate_area_and_volume(self.points, self.distances, target_min=self.target_min)
            self.progress.emit(70)
            dist = calculate_thickness_distribution(
                self.distances, self.target_min, self.target_max)
            self.progress.emit(100)
            self.finished.emit(calc, dist)
            logger.info("Calculation completed successfully.")
        except Exception as e:
            self.error.emit(str(e))
