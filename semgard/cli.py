"""Command-line interface: ``semgard scan``, ``semgard tag``, ``semgard lexicon``."""

from __future__ import annotations

import argparse
import json
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
    reports = []
    for path in args.paths:
        report = engine.scan_file(path, fmt=args.format) if path != "-" else engine.scan_text(sys.stdin.read(), fmt=args.format or "text", source="<stdin>")
        reports.append(report)
        if not args.json:
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

    if args.json:
        payload = reports[0].to_dict() if len(reports) == 1 else [report.to_dict() for report in reports]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
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
    print(f"profile {inv.profile} v{inv.version} — prefix order: {' < '.join(inv.prefix_order)}")
    for klass in inv.prefix_order:
        toks = [p for p, k in inv.prefixes.items() if k == klass]
        print(f"  prefixes[{klass}] : {', '.join(toks)}")
    print(f"  roots              : {', '.join(sorted(inv.roots))}")
    print(f"  infixes            : {', '.join(sorted(inv.infixes))}")
    print(f"  suffixes           : {', '.join(sorted(inv.suffixes))}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="semgard", description="Semantic guard against prompt injection (MorphoRepr notation).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan", help="scan files ('-' for stdin)")
    p.add_argument("paths", nargs="+")
    p.add_argument("--format", "-f", choices=["text", "log", "markdown", "field", "pdf"], default=None)
    p.add_argument("--rules", "-r", help="YAML rule file")
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true", help="show the expression for every segment")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("tag", help="tag a short text")
    p.add_argument("text")
    p.add_argument("--channel", choices=["body", "hidden", "decoded", "metadata"], default="body")
    p.set_defaults(func=cmd_tag)

    p = sub.add_parser("lexicon", help="show the semgard profile inventory")
    p.set_defaults(func=cmd_lexicon)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
