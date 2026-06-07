<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../ORC-INDEX.md -->

<!-- NAV-LEN: 0 entries | UNMRKD | Integrity-hash: e3b0c44298fc1c14 | Last-indexed: 2026-04-24T20:37:14Z -->

# Cross-phase correlations

Rules that synthesize findings across phase outputs (e.g., "TLS-weak services that are also exposed via 05 web enum" → higher severity).

Layout:
```
correlations/
├── rules/     # individual correlation rules (.sql / .py / .yml)
├── queries/   # shared SQL/DB fragments (reused by multiple rules)
└── outputs/   # generated correlations (gitignored)
```

Execution model (TBD as rules accumulate): runs after 07_service_verify, reads MSF workspace DB + phase outputs, writes summarized findings to `outputs/`.

Empty on purpose.

<!-- L2 NAV:v1 → ../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
