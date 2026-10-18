# Default COE and IOIT menu import

Authoritative source: `data/AISSMS_Canteen_Menu.xlsx` (uploaded 18 Oct 2026). It contains distinct `IOIT Canteen`, `COE Canteen`, and `Notes & Verification` worksheets. `data/menu_seed_draft.json` is a convenience transcription for initial development and must be compared to the source before seeding.

- Seed separately to IOIT Canteen (P.R. Enterprises) and COE Canteen; never combine pricing between tenants.
- Maintain source sheet and row traceability, category/name/price and COE size variants. Only legitimate numeric prices become paise. Dash/em dash and `Verify` are not zero prices.
- **Initially unavailable for ordering:** verify real price, units and size naming, station assignment, canteen approval and operating hours before enabling each item. A blank or guessed price must never be accepted by checkout.
- Build a one-time/idempotent seed command keyed by stable source IDs. Do not reset staff changes, archived state, images, station mappings or updated prices on repeated import.
- Allow staff editing through existing dashboard menu CRUD and station-assignment controls. Do not add an Excel uploader merely because seed comes from Excel.
- Item display category is separate from the preparation station. An item called Coffee may be in Beverages but routed to Snacks if the operator chooses.
- Uploading file is not an instruction to push private credentials or merchant details to GitHub. Menu file can be committed with user authorization.
