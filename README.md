# AISSMS Campus Canteen — Codex production engineering handoff

**Updated:** 18 October 2026. **Repository:** https://github.com/vighneshvijayjadhav-eng/CAMPUS_CANTEEN.git

## Getting started
1. Extract this ZIP and copy **contents** into the root of the official local `CAMPUS_CANTEEN` clone. Merge carefully without erasing existing code.
2. Make sure `AGENTS.md`, docs, `design-references/` (2 actual mockup images), and `data/` (original Excel workbook and draft JSON) are in place.
3. Start Codex in the repository and paste `MASTER_CODEX_PROMPT.md` into Codex.
4. Codex should implement sequentially, validate, and commit/push verified phase completions directly to `main`. Review progress logs and release blockers.

## Critical update
A student pays **once** per canteen order, receives **one six-digit pickup code**, but separate snacks, juice and meals stations collect only their assigned parts. The central admin can confirm particular handed-over items across stations. Code remains valid for uncollected lines and is consumed only on full collection or qualifying cancellation. Long-lived but revocable counter device sessions. No new walk-in billing and no Excel import UI.

## Production distinction
The requested target is production-grade software, **not** a proof-of-concept. The first real-money deployment still requires college/canteen authorization, separate gateway merchant accounts, verified settlement information, ownership/maintenance handover, and actual production readiness verification.

## Source files
- `AGENTS.md`: coding rules, including latest overrides
- `docs/PRODUCT_SPECIFICATION.md`, `docs/APPLICATION_ARCHITECTURE.md`, `docs/DECISIONS.md`: baseline and finalized rounds
- `docs/MULTI_COUNTER_WORKFLOW.md`: authoritative operational workflow
- `docs/MENU_SEED_GUIDE.md`: Excel seed rules
- `docs/PRODUCTION_READINESS.md`: acceptance and launch gates
- `design-references/*.jpg`: provided visual references
- `data/AISSMS_Canteen_Menu.xlsx`: original uploaded menu
- `data/menu_seed_draft.json`: transcription aid; prices/mappings must be verified
