"""
Parse project information from PLY filename.
Format: .../Projects/{project}/{job}/{job}#{yyyMMdd_hhmmss}#{segment}.ply
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ProjectInfo:
    """Project information extracted from filename."""
    project_name: str
    job_number: str
    scan_time: str
    segment_name: str
    original_filename: str
    parse_success: bool = True
    
    @property
    def formatted_date(self) -> str:
        """Format date as dd-MMM-yyyy."""
        if '_' in self.scan_time:
            date_str = self.scan_time.split('_')[0]
            if len(date_str) == 8:
                try:
                    dt = datetime.strptime(date_str, '%Y%m%d')
                    return dt.strftime('%d-%b-%Y')
                except ValueError:
                    pass
        return "N/A"
    
    @property
    def formatted_time(self) -> str:
        """Format time as HH:MM:SS."""
        if '_' in self.scan_time:
            time_str = self.scan_time.split('_')[1]
            if len(time_str) == 6:
                try:
                    return f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                except ValueError:
                    pass
        elif len(self.scan_time) == 6:
            return f"{self.scan_time[:2]}:{self.scan_time[2:4]}:{self.scan_time[4:6]}"
        return self.scan_time
    
    @property
    def report_date(self) -> str:
        """Get current date for report."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


FILENAME_PATTERN = re.compile(
    r"""
    ^(?P<job>[^#]+)                    # job name
    \#
    (?P<time>\d{8}_\d{6})             # yyyymmdd_hhmmss
    \#
    (?P<segment>.+)                   # segment (có thể chứa #)
    $
    """,
    re.VERBOSE
)


def parse_filename(filepath: str) -> ProjectInfo:
    """
    Parse PLY filename to extract project information.

    Expected format:
    .../Projects/{project}/{job}/{job}#{yyyMMdd_hhmmss}#{segment}.ply
    """

    # ===== Extract path info =====
    dir_path = os.path.dirname(filepath)
    job_dir = os.path.basename(dir_path)
    project_dir = os.path.basename(os.path.dirname(dir_path))

    filename = os.path.basename(filepath)
    name_without_ext, _ = os.path.splitext(filename)

    # ===== Regex parse =====
    match: Optional[re.Match] = FILENAME_PATTERN.match(name_without_ext)

    if match:
        parsed_job = match.group("job")
        scan_time = match.group("time")
        segment_name = match.group("segment")

        # Ưu tiên job từ folder (ổn định hơn)
        job_number = job_dir

        # Nếu project_dir trùng job thì coi như thiếu project
        project_name = project_dir if project_dir != parsed_job else "Unknown"

        return ProjectInfo(
            project_name=project_name,
            job_number=job_number,
            scan_time=scan_time,
            segment_name=segment_name,
            original_filename=filename,
            parse_success=True
        )

    # ===== Fallback =====
    return ProjectInfo(
        project_name=project_dir,
        job_number=job_dir,
        scan_time="N/A",
        segment_name=name_without_ext,
        original_filename=filename,
        parse_success=False
    )