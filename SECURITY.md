# Security policy

SemGard is experimental research software. Version 0.x is **not** a security boundary and must not be used as the sole protection against prompt injection. Deploy it only as one layer of a defense-in-depth architecture with data/instruction separation, least-privilege tools, and downstream action validation.

## Reporting a vulnerability

Please do not publish a working bypass or vulnerability report with sensitive details before giving the project a reasonable opportunity to assess it. Send reports to **michaellaunay@logikascium.com** with:

- the affected SemGard version or commit;
- a minimal reproducer;
- the expected and observed verdict;
- impact and, when relevant, the input format/channel.

Adversarial examples that only demonstrate an expected false negative in the experimental classifier are still useful as evaluation cases, but should be distinguished from implementation vulnerabilities such as unsafe parsing, rule-engine errors, crashes, or unintended data disclosure.
