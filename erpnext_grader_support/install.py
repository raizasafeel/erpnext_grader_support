from __future__ import annotations

import frappe
import requests
from frappe.utils import get_url
from frappe.utils.password import set_encrypted_password

from erpnext_grader_support.erpnext_grader_support.api import CONNECTION_DOCTYPE

WEBSITE_URL = "https://erpnext-grader.m.frappe.cloud"
PORTAL_TOKEN_ENDPOINT = (
	WEBSITE_URL + "/api/method/erpnext_grader.erpnext_grader.api.issue_token"
)


def after_install() -> None:
	"""ask for request token. The student then
	claims it from the portal UI via register_site."""
	site = (get_url() or "").rstrip("/")
	if not site:
		frappe.log_error("Could not determine this site's URL.", "ERPNext Grader Support")
		return


	try:
		resp = requests.post(PORTAL_TOKEN_ENDPOINT, json={"site": site}, timeout=15)
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
