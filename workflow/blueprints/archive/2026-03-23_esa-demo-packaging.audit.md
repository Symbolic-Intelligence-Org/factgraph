# Audit Log: ESA Demo Packaging

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-03-23 | scoped | Blueprint created | 4 deliverables: demo script, static HTML polish, positioning doc, walkthrough doc |
| 2026-03-23 | implementing | Phase 1 started | Converting the validated ECSS notebook flow into a standalone `examples/esa_demo.py` bundle with fixed output directories and provenance JSON export. |
| 2026-03-23 | implemented | Phase 1 completed | `python examples/esa_demo.py` now runs end-to-end and generates `esa_demo_output/` with `audit/`, `site/`, `provenance/`, and `summary.txt`. Verified on real ECSS scenarios: 5 accepted candidates, 3 provenance JSON artifacts, static site at `esa_demo_output/site/index.html`. |
| 2026-03-23 | implementing | Phase 2 scope clarified | Restricted to template/CSS/text polish only. Human-readable mission names are deferred because candidate tree DTOs do not currently carry them. ESA-specific branding is applied in the demo script, while `static_ui.py` remains generic. |
| 2026-03-23 | implemented | Phase 2 completed | Polished the static audit site with a clearer landing page, verdict/status emphasis on candidate evidence pages, and green/yellow/red certainty visuals. `examples/esa_demo.py` now resets and rebuilds `esa_demo_output/` on each run to avoid stale candidate pages. |
| 2026-03-23 | implemented | Phase 4 verification bug fixed | Static site detail pages now use filesystem-safe reversible slugs (`quote(...).replace("%", "~")`) instead of raw percent-encoded filenames, so candidate evidence links work under simple static servers used in the ESA demo flow. Verified by regenerating `esa_demo_output/` and running the full `244`-test suite. |
| 2026-03-23 | implemented | Phase 4 browser walkthrough complete | Verified all key pages via HTTP server: landing page (ESA branding, 5 runs, 5 evidence trees), candidate list (5 rows, ~ slug links work), evidence detail (hero card, verdict badge, narrative sections), certainty (score 0.4, bottleneck, weakest badge, impact bars), evidence tree (color-coded nodes, hierarchical nesting). All links functional. Blueprint complete. |
