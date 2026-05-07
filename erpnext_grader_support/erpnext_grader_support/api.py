from __future__ import annotations

import hmac

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime
from frappe.utils.password import get_decrypted_password

from erpnext_grader_support.erpnext_grader_support.checks import run_checks

CONNECTION_DOCTYPE = "ERPNext Grader Connection"


def _require_bearer() -> None:
	sent = (frappe.get_request_header("X-Grader-Token") or "").strip()
	if not sent:
		frappe.throw(_("Missing grader token."), frappe.AuthenticationError)
	stored = get_decrypted_password(
		CONNECTION_DOCTYPE, CONNECTION_DOCTYPE, "token", raise_exception=False
	)
	expiry = frappe.db.get_single_value(CONNECTION_DOCTYPE, "token_expiry")
	if not stored or not expiry or get_datetime(expiry) <= now_datetime():
		frappe.throw(_("Site not linked or token expired."), frappe.AuthenticationError)
	if not hmac.compare_digest(sent, stored):
		frappe.throw(_("Invalid grader token."), frappe.AuthenticationError)


@frappe.whitelist(allow_guest=True)
def run_checks_api(checks: dict | None = None) -> dict:
	"""checks token for suth and runs checks if valid."""
	_require_bearer()
	return run_checks(checks or {})
