"""Pipeline step 5: semantic tagging of segments as MorphoRepr expressions.

A tagger receives a ``Segment`` and returns an ``Expression`` from the SemGard
profile, for example ``0.83·vi-mal-regul-u + 0.41·elig-u``.

Two implementations:

- ``HeuristicTagger`` — deterministic, closed lexicons, no dependency. It is
  the baseline and pseudo-label generator used to bootstrap a corpus;
- ``ModelTagger`` — interface for a small multi-head encoder (ModernBERT /
  DeBERTa-v3, ONNX/int8) that predicts form, addressee, polarity, root,
  causative, act, and confidence; to be trained on the annotated corpus.

In both cases output goes through ``parser.make_word``: an unparsable chain is
never emitted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from .classifiers import directive_mood
from .inventory import Inventory
from .normalize import Segment
from .parser import Expression, Term, make_word

# --- closed French/English lexicons ------------------------------------------

_AI_TERMS = re.compile(
    r"\b(?:assistant|ai|a\.i\.|ia|chatbot|bot|llm|language\s+model|mod[èe]le(?:\s+de\s+langage)?|model|claude|chatgpt|gpt(?:-?\d)?|"
    r"copilot|gemini|llama|mistral|agent|system\s+prompt|syst[èe]me|your\s+(?:instructions|guidelines|programming|training)|"
    r"tes\s+(?:instructions|consignes|r[èe]gles))\b",
    re.I,
)
_SECOND_PERSON = re.compile(r"\b(?:you|your|yourself|tu|te|toi|ton|ta|tes|vous|votre|vos)\b", re.I)

_TOPICS: dict[str, re.Pattern[str]] = {
    "regul": re.compile(
        r"\b(?:instructions?|consignes?|r[èe]gles?|rules?|guidelines?|polic(?:y|ies)|restrictions?|guardrails?|"
        r"safety\s+(?:rules|filters?)|filtres?|system\s+prompt|prompt\s+syst[èe]me|directives?|contraintes?|limitations?|"
        r"previous\s+(?:instructions|prompts?|context)|above\s+instructions|prior\s+instructions|developer\s+message)\b",
        re.I,
    ),
    "rol": re.compile(
        r"\b(?:you\s+are\s+now|act\s+as|pretend\s+(?:to\s+be|that\s+you|you)|roleplay|role-play|play\s+the\s+role|persona|"
        r"jailbreak|dan\b|do\s+anything\s+now|developer\s+mode|unfiltered|uncensored|no\s+restrictions|without\s+restrictions|"
        r"tu\s+es\s+(?:d[ée]sormais|maintenant)|vous\s+[êe]tes\s+(?:d[ée]sormais|maintenant)|joue\s+le\s+r[ôo]le|"
        r"fais\s+comme\s+si|incarne|deviens|mode\s+d[ée]veloppeur|sans\s+restrictions?|sans\s+filtre)\b",
        re.I,
    ),
    "ilo": re.compile(
        r"\b(?:execute|run|call|invoke|curl|wget|fetch|browse|navigate|visit|open\s+(?:the\s+)?(?:url|link|page)|send\s+(?:an?\s+)?(?:email|mail|request|message)|"
        r"post\s+to|upload|download|install|tool|function\s+call|shell|bash|command|script|"
        r"ex[ée]cute|lance|appelle|envoie\s+(?:un\s+)?(?:mail|e-mail|courriel|message|requ[êe]te)|t[ée]l[ée]charge|installe|outil|commande)\b",
        re.I,
    ),
    "sekr": re.compile(
        r"\b(?:api\s*keys?|secret\s*keys?|password|passwd|mot\s+de\s+passe|credentials?|identifiants?|tokens?|jetons?|"
        r"private\s+key|cl[ée]s?\s+(?:priv[ée]e|api|secr[èe]te)|confidential|confidentiel(?:le)?s?|"
        r"(?:contents?\s+of\s+)?(?:your|the)\s+(?:system\s+)?prompt|reveal\s+(?:your|the)|"
        r"personal\s+data|donn[ée]es\s+personnelles|ssn|social\s+security|credit\s+card|carte\s+bancaire|iban|"
        r"env(?:ironment)?\s+variables?|\.env\b|secrets?)\b",
        re.I,
    ),
    "elig": re.compile(
        r"\b(?:respond|reply|answer|output|print|say|write|translate|summari[sz]e|repeat|format|r[ée]ponds?|r[ée]pondez|"
        r"affiche|[ée]cris|dis|traduis|r[ée]sume|r[ée]p[èe]te|ta\s+r[ée]ponse|your\s+(?:response|answer|output|reply)|"
        r"in\s+(?:json|markdown|french|english|fran[çc]ais|anglais)|en\s+(?:json|markdown|fran[çc]ais|anglais))\b",
        re.I,
    ),
}
_OVERRIDE = re.compile(
    r"\b(?:ignore|disregard|forget|override|bypass|circumvent|skip|drop|discard|n[o']\s+longer\s+(?:apply|follow)|"
    r"ignorez?|oubliez?|contournez?|n'appliquez?\s+plus|ne\s+(?:suis|suivez|respecte|respectez|tiens|tenez)\s+plus|"
    r"sans\s+(?:tenir\s+compte|restriction)|without\s+(?:restriction|limitation|regard))\b",
    re.I,
)
_SUPPRESS = re.compile(
    r"\b(?:do\s+not|don't|never|without)\s+(?:mention|tell|warn|reveal|disclose|say|inform|alert|flag|report|explain)|"
    r"\bne\s+(?:mentionne|dis|r[ée]v[èe]le|signale|pr[ée]viens|avertis|explique)[a-z]*\s+(?:pas|jamais|rien)|"
    r"\bsans\s+(?:avertir|avertissement|pr[ée]venir|le\s+dire|mentionner|signaler|disclaimer)\b|\bwithout\s+(?:any\s+)?(?:warning|disclaimer|caveat)s?\b",
    re.I,
)
_HYPOTHETICAL = re.compile(
    r"\b(?:imagine|pretend|suppose|hypothetical(?:ly)?|let's\s+play|let's\s+pretend|in\s+this\s+(?:game|scenario|story)|"
    r"as\s+if|roleplay|role-play|act\s+as|imaginons|imagine[sz]?\s+que|suppose[sz]?\s+que|jouons|fais\s+comme\s+si|"
    r"dans\s+ce\s+(?:jeu|sc[ée]nario|r[ée]cit)|si\s+tu\s+[ée]tais|if\s+you\s+were)\b",
    re.I,
)
_CAUSATIVE = re.compile(
    r"\b(?:make\s+(?:it|him|her|them|the\s+\w+)\s+\w+|have\s+(?:it|the\s+\w+)\s+\w+|get\s+(?:it|the\s+\w+)\s+to|"
    r"send\s+(?:it|them|the|all|every)|forward|leak|exfiltrate|transmit|export|dump|"
    r"fais\s+(?:en\s+sorte|le|la|les)|envoie|transmets|exporte|fais\s+fuiter)\b",
    re.I,
)


def _clip(x: float, lo: float = 0.05, hi: float = 0.98) -> float:
    return round(max(lo, min(hi, x)), 2)


class Tagger(Protocol):
    def tag(self, segment: Segment) -> Expression: ...


@dataclass
class HeuristicTagger:
    """Deterministic v0 tagger (baseline and pseudo-label generator)."""

    inventory: Inventory = field(default_factory=Inventory.semgard)
    max_terms: int = 3

    def _form_prefix(self, seg: Segment) -> tuple[str, ...]:
        if seg.channel == "decoded":
            return ("kod",)
        if seg.channel in ("hidden", "metadata") or seg.zero_width_removed:
            return ("kash",)
        return ()

    def tag(self, seg: Segment) -> Expression:
        text = seg.text
        dm = directive_mood(text)
        directive = float(dm["score"])  # type: ignore[arg-type]
        hypothetical = bool(_HYPOTHETICAL.search(text))
        ai_term = bool(_AI_TERMS.search(text))
        second = bool(_SECOND_PERSON.search(text))
        # An imperative targets the second person even without an explicit pronoun.
        imperative = any(str(e).startswith("imperative_lead") for e in dm["evidence"])  # type: ignore[union-attr]
        override = bool(_OVERRIDE.search(text))
        suppress = bool(_SUPPRESS.search(text))
        causative = bool(_CAUSATIVE.search(text))

        topic_hits = {root: len(rx.findall(text)) for root, rx in _TOPICS.items()}
        topic_hits = {r: n for r, n in topic_hits.items() if n}

        # Speech act → suffix.
        if hypothetical and (directive >= 0.25 or second):
            suffix = "us"
        elif directive >= 0.5:
            suffix = "u"
        elif len(text.split()) < 3:
            suffix = "o"
        else:
            suffix = "as"

        # Addressee: ``vi-`` for an AI term, or second person + an intrinsically machine topic.
        machine_topic = bool({"regul", "rol", "elig"} & topic_hits.keys())
        addressee = 0.0
        if ai_term and (second or suffix in ("u", "us")):
            addressee = 0.9
        elif ai_term:
            addressee = 0.6
        elif (second or imperative) and machine_topic and suffix in ("u", "us"):
            addressee = 0.55
        vi = ("vi",) if addressee >= 0.5 else ()

        form = self._form_prefix(seg)
        evidence: dict[str, object] = {
            "directive": dm,
            "hypothetical": hypothetical,
            "ai_term": ai_term,
            "second_person": second,
            "imperative": imperative,
            "override": override,
            "suppress": suppress,
            "causative": causative,
            "topics": topic_hits,
        }
        seg.tags["evidence"] = evidence

        terms: list[Term] = []
        if not topic_hits:
            coef = _clip(0.9 - 0.35 * directive - (0.15 if addressee else 0.0))
            terms.append(Term(coef, make_word(self.inventory, "dat", prefixes=form, suffix=suffix)))
            return Expression(tuple(terms))

        for root, n in sorted(topic_hits.items(), key=lambda kv: -kv[1])[: self.max_terms]:
            polarity: tuple[str, ...] = ()
            if root in ("regul", "rol") and override:
                polarity = ("mal",)
            elif root in ("regul", "elig", "sekr") and suppress:
                polarity = ("ne",)
            infixes: tuple[str, ...] = ("ig",) if (causative and root in ("sekr", "ilo", "elig")) else ()
            coef = _clip(0.35 + 0.12 * min(n, 3) + 0.25 * addressee + 0.25 * directive + (0.1 if polarity else 0.0))
            terms.append(Term(coef, make_word(self.inventory, root, prefixes=(*form, *vi, *polarity), infixes=infixes, suffix=suffix)))
        terms.sort(key=lambda t: -t.coefficient)
        return Expression(tuple(terms))


@dataclass
class ModelTagger:
    """Interface for a neural tagger (small multi-head encoder).

    Contract: ``model_path`` points to an exported model with ``form``,
    ``addressee``, ``polarity``, ``root``, ``causative``, and ``act`` heads;
    output is converted to chains through ``make_word`` and the coefficient is
    the calibrated root probability. Not implemented in v0.1 because the
    training corpus does not exist yet (see the specification, §5).
    """

    model_path: str
    inventory: Inventory = field(default_factory=Inventory.semgard)

    def tag(self, segment: Segment) -> Expression:
        raise NotImplementedError("ModelTagger: training is planned after the corpus is assembled (spec §5)")
