import pytest

from semgard.inventory import Inventory
from semgard.parser import ParseError, parse_expression, parse_word

# Forms from the MorphoRepr v0.30 paper (Section 3.4 and Appendix A): parser regression
# coverage against the SAE profile.
PAPER_WORDS = [
    ("ag-is", (), "ag", (), "is"),
    ("mal-o", (), "mal", (), "o"),
    ("ne-a", (), "ne", (), "a"),
    ("soc-ant-o", (), "soc", ("ant",), "o"),
    ("ag-int-a", (), "ag", ("int",), "a"),
    ("dat-ad-o", (), "dat", ("ad",), "o"),
    ("mal-emo-a", ("mal",), "emo", (), "a"),
    ("ne-soc-a", ("ne",), "soc", (), "a"),
    ("mal-far-int-e", ("mal",), "far", ("int",), "e"),
    ("pens-ad-is", (), "pens", ("ad",), "is"),
    ("mal-ne-o", ("mal",), "ne", (), "o"),
]


@pytest.mark.parametrize("chain,prefixes,root,infixes,suffix", PAPER_WORDS)
def test_sae_profile_parses_paper_words(chain, prefixes, root, infixes, suffix):
    w = parse_word(chain, Inventory.sae())
    assert (w.prefixes, w.root, w.infixes, w.suffix) == (prefixes, root, infixes, suffix)
    assert w.chain == chain


def test_sae_expression_roundtrip():
    e = parse_expression("0.86·mal-emo-a + 0.42·ne-soc-a", Inventory.sae())
    assert str(e) == "0.86·mal-emo-a + 0.42·ne-soc-a"
    assert e.chains == ("mal-emo-a", "ne-soc-a")


@pytest.mark.parametrize(
    "chain",
    ["vi-mal-regul-u", "kash-vi-elig-u", "kod-vi-sekr-ig-u", "dat-as", "vi-rol-us", "sekr-ig-u", "ne-elig-u"],
)
def test_semgard_profile_accepts_canonical_chains(inv, chain):
    assert parse_word(chain, inv).chain == chain


@pytest.mark.parametrize(
    "chain",
    [
        "vi-kash-regul-u",  # non-canonical class order (form < addressee)
        "mal-vi-regul-u",  # polarity before addressee
        "regul",  # no suffix
        "vi-foo-u",  # free root forbidden in the closed profile
        "vi-regul-ad-u",  # infix outside the profile
        "vi-regul-is",  # suffix outside the profile
    ],
)
def test_semgard_profile_rejects(inv, chain):
    with pytest.raises(ParseError):
        parse_word(chain, inv)


def test_coefficient_bounds(inv):
    with pytest.raises(ParseError):
        parse_expression("0.00·dat-as", inv)
    with pytest.raises(ParseError):
        parse_expression("1.50·dat-as", inv)
    assert parse_expression("1.00·dat-as", inv).terms[0].coefficient == 1.0


def test_expression_rejects_empty_terms(inv):
    with pytest.raises(ParseError):
        parse_expression("0.80·dat-as +", inv)
    with pytest.raises(ParseError):
        parse_expression("0.80·dat-as ++ 0.50·sekr-o", inv)


def test_expression_requires_descending_confidence(inv):
    with pytest.raises(ParseError):
        parse_expression("0.40·dat-as + 0.80·sekr-o", inv)
    assert parse_expression("0.80·sekr-o + 0.40·dat-as", inv).chains == ("sekr-o", "dat-as")


def test_inventory_rejects_collisions():
    with pytest.raises(ValueError):
        Inventory.from_dict({"prefixes": {"a": ["x"], "b": ["x"]}, "roots": [], "infixes": [], "suffixes": ["u"]})
    with pytest.raises(ValueError):
        Inventory.from_dict({"prefixes": {}, "roots": ["u"], "infixes": [], "suffixes": ["u"]})
    with pytest.raises(ValueError):
        Inventory.from_dict({"prefixes": {"a": ["x"]}, "roots": [], "infixes": ["x"], "suffixes": ["u"]})
    with pytest.raises(ValueError):
        Inventory.from_dict({"prefixes": {"a": ["x"]}, "roots": [], "infixes": [], "suffixes": ["u"], "prefix_order": ["missing"]})
