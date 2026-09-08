"""CLI : ``semgard scan``, ``semgard tag``, ``semgard lexicon``."""

from __future__ import annotations

import argparse
import sys

from .engine import Engine
from .inventory import Inventory
from .normalize import Segment
from .rules import RuleSet
from .tagger import HeuristicTagger


def _engine(args: argparse.Namespace) -> Engine:
    ruleset = RuleSet.from_yaml(args.rules) if getattr(args, "rules", None) else RuleSet.default()
    return Engine(tagger=HeuristicTagger(), ruleset=ruleset)


def cmd_scan(args: argparse.Namespace) -> int:
    engine = _engine(args)
    exit_code = 0
    for path in args.paths:
        report = engine.scan_file(path, fmt=args.format) if path != "-" else engine.scan_text(sys.stdin.read(), fmt=args.format or "text", source="<stdin>")
        if args.json:
            print(report.to_json())
        else:
            print(f"== {report.source} : {report.verdict.upper()}")
            for f in report.findings:
                seg = report.segments[f.segment_index]
                print(f"  [{f.severity:>8}] {f.action:<10} {f.rule_id:<28} γ={f.gamma:.2f}  {f.matched}")
                print(f"             {seg.channel}/{seg.kind} @{seg.start}: {seg.text[:100]!r}")
            if args.verbose:
                for i, (s, e) in enumerate(zip(report.segments, report.expressions)):
                    print(f"  {i:3} {s.channel:<8} {e}   {s.text[:60]!r}")
        if report.verdict in ("quarantine", "block"):
            exit_code = 2
        elif report.verdict == "mark" and exit_code == 0:
            exit_code = 1
    return exit_code


def cmd_tag(args: argparse.Namespace) -> int:
    tagger = HeuristicTagger()
    seg = Segment(args.text, 0, len(args.text), channel=args.channel, kind="field")
    from .normalize import normalize_segments

    for s in normalize_segments([seg]):
        print(f"{s.channel:<8} {tagger.tag(s)}")
    return 0


def cmd_lexicon(args: argparse.Namespace) -> int:
    inv = Inventory.semgard()
    print(f"profil {inv.profile} v{inv.version} — ordre des préfixes : {' < '.join(inv.prefix_order)}")
    for klass in inv.prefix_order:
        toks = [p for p, k in inv.prefixes.items() if k == klass]
        print(f"  préfixes[{klass}] : {', '.join(toks)}")
    print(f"  racines           : {', '.join(sorted(inv.roots))}")
    print(f"  infixes           : {', '.join(sorted(inv.infixes))}")
    print(f"  suffixes          : {', '.join(sorted(inv.suffixes))}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="semgard", description="Filtre sémantique contre l'injection de prompt (notation MorphoRepr).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan", help="analyser des fichiers ('-' pour stdin)")
    p.add_argument("paths", nargs="+")
    p.add_argument("--format", "-f", choices=["text", "log", "markdown", "field", "pdf"], default=None)
    p.add_argument("--rules", "-r", help="fichier YAML de règles")
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true", help="afficher l'expression de chaque segment")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("tag", help="étiqueter un texte court")
    p.add_argument("text")
    p.add_argument("--channel", choices=["body", "hidden", "decoded", "metadata"], default="body")
    p.set_defaults(func=cmd_tag)

    p = sub.add_parser("lexicon", help="afficher l'inventaire du profil semgard")
    p.set_defaults(func=cmd_lexicon)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
