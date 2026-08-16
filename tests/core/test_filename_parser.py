from pps_report.core.filename_parser import parse_filename


def test_valid_filename():
    path = "/data/Projects/ProjA/Job123/Job123#20250414_153000#seg1.ply"
    info = parse_filename(path)

    assert info.parse_success
    assert info.project_name == "ProjA"
    assert info.job_number == "Job123"
    assert info.scan_time == "20250414_153000"
    assert info.segment_name == "seg1"


def test_segment_with_hash():
    path = "/data/Projects/ProjA/Job123/Job123#20250414_153000#seg#a.ply"
    info = parse_filename(path)

    assert info.parse_success
    assert info.segment_name == "seg#a"


def test_invalid_filename():
    path = "/data/Projects/ProjA/Job123/random.ply"
    info = parse_filename(path)

    assert not info.parse_success
    assert info.scan_time == "N/A"
