"""SemGard — semantic guard against prompt injection.

Regular expressions over morphemic tags (the MorphoRepr ``semgard`` profile)
emitted by a tagger (v0 heuristic, small model planned).
"""

from .engine import Engine, Report
from .inventory import Inventory
from .parser import Expression, ParseError, parse_expression, parse_word
from .rules import Finding, Rule, RuleSet
from .tagger import HeuristicTagger, ModelTagger

__version__ = "0.1.0"
__all__ = [
    "Engine",
    "Report",
    "Inventory",
    "Expression",
    "ParseError",
    "parse_expression",
    "parse_word",
    "Finding",
    "Rule",
    "RuleSet",
    "HeuristicTagger",
    "ModelTagger",
]
