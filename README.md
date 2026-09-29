# ERPNext Assignment Checks

Support app for the ERPNext assignment on Frappe School (v2). Install it on a student's Frappe Cloud trial site so the grader portal (`erpnext_assignment_portal`) can count records. The app stores nothing and adds no doctypes, pages, or UI.

Requires `erpnext`, Python >= 3.10, and Frappe v15 or v16.

## Install

On a Frappe Cloud trial, add the app from this repository's `v2` branch (Apps > Add App > from GitHub), then deploy. Elsewhere:

```
bench get-app <repo url> --branch v2
bench --site <site> install-app erpnext_assignment_checks
```

## What it exposes

Two guest-accessible POST endpoints. Both require a valid signature, and the request host must equal the site's own host.

| Endpoint | Body | Returns |
| --- | --- | --- |
| `erpnext_assignment_checks.api.verify_owner` | `{"email": ...}` | `{"ok": true/false}`. True only for an enabled user with that email who is a System Manager. |
| `erpnext_assignment_checks.api.run_checks` | `{"checks": [...]}` | `{"results": [...]}` with one `{check_id, found_count}` or `{check_id, error}` per check. |

Each check names a target doctype and a list of `[field, operator, value]` filters. The app counts matching documents with `frappe.get_all`. A check error is one of `not_allowed`, `invalid`, or `timeout`.

## What it never returns

Field values, document names, user details other than a yes/no, or error text. Only integer counts and fixed error codes leave the site.

## Signing

Every request carries `X-Grader-Key-Id`, `X-Grader-Timestamp`, and `X-Grader-Signature`. The signature is Ed25519 over the host, timestamp, path, and SHA-256 of the body. A request is refused if the key id is unknown, the timestamp is more than 300 seconds off, the body is over 256 KB, or the signature is invalid. Refusals are a generic 403.

Public keys live in `PUBLIC_KEYS` in `erpnext_assignment_checks/signing.py`, keyed by key id. The production key id is `grader-2026-10`. Only public keys are stored here; the private key lives on the portal site and is never committed. `PUBLIC_KEYS` is empty until the production public key is added, and until then every request is refused.

## Limits

- At most 300 checks per request.
- A count is capped at 1000.
- 20 seconds total per request. Checks past the deadline return `timeout`.
- Only doctypes and fields listed in `erpnext_assignment_checks/allowlist.py` can be counted. Anything else returns `not_allowed`. `tools/print_allowlist.py` builds the list from the v1 check data.

## Development

Uses `pre-commit` for ruff and formatting:

```
cd apps/erpnext_assignment_checks
pre-commit install
```

License: MIT
