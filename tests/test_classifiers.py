from semgard.classifiers.calibration.run_calibration import run


def test_directive_mood_calibration_set_passes():
    stats = run("directive_mood")
    assert stats["fn"] == 0 and stats["fp"] == 0, stats
