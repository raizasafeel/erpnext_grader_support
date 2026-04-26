from __future__ import annotations

import frappe
import requests
from frappe.utils.password import set_encrypted_password

from erpnext_grader_support.erpnext_grader_support.api import CONNECTION_DOCTYPE
WEBSITE_URL = "https://frappeschool.com"
PORTAL_TOKEN_ENDPOINT = (
	WEBSITE_URL + "/api/method/erpnext_grader.erpnext_grader.api.issue_token"
)

def after_install() -> None:
	"""
	ask website for a token on installation
	"""
	email = (frappe.conf.get("student_email") or "").strip()
	if not email:
		frappe.log_error(
			"student_email not set in site_config.json; skipping grader enrollment.",
			"ERPNext Grader Support",
		)
		return

	try:
		resp = requests.post(PORTAL_TOKEN_ENDPOINT, json={"email": email}, timeout=50)
	except requests.RequestException as e:
		frappe.log_error(f"Portal unreachable: {e}", "ERPNext Grader Support")
		return

	if resp.status_code != 200:
		frappe.log_error(
			f"Portal returned {resp.status_code}: {resp.text[:300]}",
			"ERPNext Grader Support",
		)
		return

	msg = (resp.json() or {}).get("message") or {}
	token, expiry = msg.get("token"), msg.get("expires_at")
	if not token or not expiry:
		frappe.log_error(
			f"Portal response missing token/expires_at: {msg}",
			"ERPNext Grader Support",
		)
		return

	frappe.db.set_single_value(CONNECTION_DOCTYPE, "token_expiry", expiry)
	set_encrypted_password(CONNECTION_DOCTYPE, CONNECTION_DOCTYPE, token, "token")
	frappe.db.commit()
