import json

import frappe
from frappe import _

from erpnext_assignment_checks import checks as check_runner
from erpnext_assignment_checks.signing import require_signature


def _signed_body() -> dict:
	require_signature()
	try:
		body = json.loads(frappe.request.get_data())
	except ValueError:
		body = None
	if not isinstance(body, dict):
		frappe.throw(_("Forbidden"), frappe.PermissionError)
	return body


# nosemgrep: guest-whitelisted-method -- guest by design; require_signature() gates every call
@frappe.whitelist(allow_guest=True, methods=["POST"])
def verify_owner() -> dict:
	email = _signed_body().get("email")
	if not isinstance(email, str) or not email:
		return {"ok": False}
	user = frappe.db.get_value("User", {"email": email, "enabled": 1}, "name")
	return {"ok": bool(user) and "System Manager" in frappe.get_roles(user)}


# nosemgrep: guest-whitelisted-method -- guest by design; require_signature() gates every call
@frappe.whitelist(allow_guest=True, methods=["POST"])
def run_checks() -> dict:
	checks = _signed_body().get("checks")
	if not isinstance(checks, list):
		frappe.throw(_("Forbidden"), frappe.PermissionError)
	return {"results": check_runner.run_checks(checks)}
