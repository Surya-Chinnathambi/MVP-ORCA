<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../ORC-INDEX.md -->

<!-- NAV-LEN: 0 entries | UNMRKD | Integrity-hash: e3b0c44298fc1c14 | Last-indexed: 2026-04-24T20:37:14Z -->

# Custom modules

Per-script extensions: custom NSE scripts, tier configs, host filters, customer-specific scope rules, etc.

Layout:
```
modules/
├── 03/     # 03_comp_scan extensions
├── 05/     # 05_web_enum extensions
└── 06/     # 06_wpscan extensions
```

Each script's modules dir should have its own README describing:
- What slot(s) in the parent script consume these modules
- Naming convention
- How to enable / disable

Empty on purpose — populate as engagement-specific customizations accumulate.

<!-- L2 NAV:v1 → ../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
