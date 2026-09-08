"""``directive_mood`` classifier: is the segment an instruction?

Shared deliverable with MorphoRepr: the ``directive_mood`` output property is
the measurable counterpart of the volitive ``-u`` suffix, absent from the four
robust v0.30 properties (negation, tense, code, conditional modality). The same
code is intended to be contributed to ``morphorepr/classifiers/directive_mood.py``
with its calibration file.

Dependency-free v1 heuristic for French and English. Signals:

1. an imperative verb at the start of the segment (closed lexicon);
2. a deontic construction or performative assignment (``you must``, ``tu dois``,
   ``you are now``, ``tu es désormais``);
3. a temporal reset marker (``from now on``, ``désormais``);
4. a negative imperative (``do not``, ``ne … pas`` + verb);
5. a constrained-output formula (``respond only with``, ``réponds uniquement``).

The score aggregates these signals; ``present`` is true at or above 0.5.
Calibrate it on ``calibration/directive_mood_test.json`` before any pilot.
"""

from __future__ import annotations

import re

IMPERATIVE_VERBS_EN = (
    "ignore|disregard|forget|override|bypass|skip|reveal|print|output|respond|answer|reply|send|email|post|execute|run|"
    "call|fetch|open|visit|browse|do|act|pretend|behave|roleplay|translate|write|say|tell|show|display|delete|remove|stop|"
    "begin|start|continue|repeat|summarize|summarise|include|insert|add|append|return|give|provide|list|dump|leak|"
    "exfiltrate|copy|paste|use|assume|imagine|suppose|consider|treat|switch|change|set|enable|disable|generate|create|"
    "make|ensure|comply|obey|follow|read|note|remember|keep"
)
IMPERATIVE_VERBS_FR = (
    "ignore|ignorez|oublie|oubliez|contourne|contournez|révèle|révélez|revele|revelez|affiche|affichez|réponds|répondez|"
    "reponds|repondez|envoie|envoyez|exécute|exécutez|execute|executez|lance|lancez|appelle|appelez|ouvre|ouvrez|"
    "fais|faites|agis|agissez|joue|jouez|traduis|traduisez|écris|écrivez|ecris|ecrivez|dis|dites|montre|montrez|"
    "supprime|supprimez|efface|effacez|arrête|arrêtez|arrete|arretez|commence|commencez|continue|continuez|répète|"
    "répétez|repete|repetez|résume|résumez|resume|resumez|inclus|incluez|ajoute|ajoutez|renvoie|renvoyez|donne|donnez|"
    "fournis|fournissez|liste|listez|copie|copiez|utilise|utilisez|imagine|imaginez|suppose|supposez|considère|"
    "considérez|considere|considerez|traite|traitez|passe|passez|change|changez|active|activez|désactive|désactivez|"
    "génère|générez|genere|generez|crée|créez|cree|creez|obéis|obéissez|obeis|obeissez|suis|suivez|lis|lisez|note|notez|"
    "retiens|retenez|garde|gardez|adopte|adoptez|deviens|devenez|sois|soyez"
)

_LEAD = r"^(?:[\W_]*(?:please|s'il te pla[iî]t|s'il vous pla[iî]t|svp|now|maintenant|first|then|also|ensuite|d'abord|aussi)[,\s]*)*"
_RE_IMPERATIVE = re.compile(_LEAD + rf"(?:{IMPERATIVE_VERBS_EN}|{IMPERATIVE_VERBS_FR})\b", re.I)
_RE_DEONTIC = re.compile(
    r"\b(?:you\s+(?:must|should|need\s+to|have\s+to|are\s+(?:required|obliged|now)\s+to|will\s+now|shall|are\s+now)|"
    r"tu\s+(?:dois|devras|vas\s+maintenant|es\s+(?:d[ée]sormais|maintenant))|"
    r"vous\s+(?:devez|devrez|allez\s+maintenant|[êe]tes\s+(?:d[ée]sormais|maintenant))|il\s+faut\s+que\s+(?:tu|vous)|"
    r"it\s+is\s+(?:mandatory|required)\s+that\s+you)\b",
    re.I,
)
_RE_TEMPORAL_BREAK = re.compile(r"\b(?:from\s+now\s+on|starting\s+now|as\s+of\s+now|d[ée]sormais|[àa]\s+partir\s+de\s+maintenant|dor[ée]navant)\b", re.I)
_RE_NEG_IMPERATIVE = re.compile(
    rf"(?:^|[\s,;:])(?:do\s+not|don't|never|ne\s+(?:{IMPERATIVE_VERBS_FR})\s+(?:pas|jamais|plus)|n'(?:{IMPERATIVE_VERBS_FR})\s+(?:pas|jamais|plus))\b",
    re.I,
)
_RE_OUTPUT_CONSTRAINT = re.compile(
    r"\b(?:respond|reply|answer|output)\s+(?:only|solely|exclusively|just)\s+(?:with|in)|"
    r"\b(?:r[ée]ponds|r[ée]pondez)\s+(?:uniquement|seulement|exclusivement)|"
    r"\byour\s+(?:only\s+)?(?:response|answer|output)\s+(?:must|should|will)\b|\bta\s+r[ée]ponse\s+(?:doit|devra)\b",
    re.I,
)

WEIGHTS = {
    "imperative_lead": 0.55,
    "deontic": 0.5,
    "temporal_break": 0.25,
    "negative_imperative": 0.4,
    "output_constraint": 0.5,
}


def classify(text: str) -> dict[str, object]:
    evidence: list[str] = []
    score = 0.0
    checks = (
        ("imperative_lead", _RE_IMPERATIVE),
        ("deontic", _RE_DEONTIC),
        ("temporal_break", _RE_TEMPORAL_BREAK),
        ("negative_imperative", _RE_NEG_IMPERATIVE),
        ("output_constraint", _RE_OUTPUT_CONSTRAINT),
    )
    for name, regex in checks:
        m = regex.search(text)
        if m:
            evidence.append(f"{name}:{m.group(0).strip()}")
            score += WEIGHTS[name]
    score = min(score, 1.0)
    return {"present": score >= 0.5, "score": round(score, 2), "evidence": evidence}
