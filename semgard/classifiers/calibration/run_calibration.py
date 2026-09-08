"""Calibration d'un classifieur déterministe : matrice de confusion sur son jeu de test.

Usage : python -m semgard.classifiers.calibration.run_calibration directive_mood
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def run(name: str) -> dict[str, float | int]:
    module = importlib.import_module(f"semgard.classifiers.{name}")
    data = json.loads((Path(__file__).parent / f"{name}_test.json").read_text(encoding="utf-8"))
    tp = fp = tn = fn = 0
    for ex in data["examples"]:
        got = bool(module.classify(ex["text"])["present"])
        exp = bool(ex["expected"])
        if got and exp:
            tp += 1
        elif got and not exp:
            fp += 1
            print(f"  FP : {ex['text']!r}")
        elif not got and exp:
            fn += 1
            print(f"  FN : {ex['text']!r}")
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


if __name__ == "__main__":
    for name in sys.argv[1:] or ["directive_mood"]:
        print(f"== {name}")
        print(json.dumps(run(name), indent=2))
