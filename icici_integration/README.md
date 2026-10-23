# ICICI Trade API Integration (Odoo 20 Enterprise)

Menus: ICICI Trade > IRM List, Settled IRM, Outstanding Shipping Bills, Outstanding Remittance,
Fetch from ICICI (one wizard per API), Configuration (managers only).

## Setup
1. Install the module (needs the `requests` Python package).
2. ICICI Trade > Configuration: environment (UAT/Production), `apikey`, `x-session-key`, corpId, ieCode,
   and the defaults for the outstanding-remittance API. API URLs are editable per API and environment.
3. The Odoo server's public IP must be whitelisted on the ICICI portal (Technical Details).

## Behaviour
- Records are keyed by remittance ref / shipping bill no / GRS ref per company; a repeated fetch never duplicates.
- A SHA-256 of each API item detects changes: unchanged items are left alone, changed ones are updated and the
  changed fields plus the new response are logged in the chatter.
- Every response field is stored as a field; the full item JSON is kept in "API Response" and posted to the chatter.
- Shipping bills: list from the list API; the "Fetch Details" button on the form calls the details API.

## Open items (not documented by ICICI)
- How `x-session-key` is generated and whether payloads are encrypted: the only places to change are
  `_get_session_key`, `_prepare_body` and `_parse_response` in `models/icici_config.py`.
- URL of the Outstanding Shipping Bill List API (blank by default).
- Shipping Bill UAT host: documents say `icicibank.com`, the others `icici.bank.in`.
- Targets Odoo 20: security uses the new `security/ir.access.csv` (operation + domain columns, record rules merged in) and SQL constraints use `models.Constraint`. Not yet installed on a live Odoo 20 instance.
