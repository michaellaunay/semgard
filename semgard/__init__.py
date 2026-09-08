"""SemGard — filtre sémantique contre l'injection de prompt.

Regex sur des étiquettes morphémiques (profil MorphoRepr « semgard ») émises
par un étiqueteur (heuristique v0, petit modèle à venir).
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
