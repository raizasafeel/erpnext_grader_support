import base64
import json
import time
from unittest.mock import patch

import frappe
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

try:
	from frappe.tests import IntegrationTestCase
except ImportError:
	from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from erpnext_assignment_checks import api, signing

KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PUB = KEY.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
HOST = "trial.m.frappe.cloud"


def fake_request(method: str, payload, signed: bool = True) -> None:
	path = f"/api/method/erpnext_assignment_checks.api.{method}"
	body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
	headers = {"Content-Type": "application/json"}
	if signed:
		ts = str(int(time.time()))
		sig = KEY.sign(signing.signing_message(HOST, ts, path, body))
		headers |= {
			"X-Grader-Key-Id": "test",
			"X-Grader-Timestamp": ts,
			"X-Grader-Signature": base64.b64encode(sig).decode(),
		}
	env = EnvironBuilder(method="POST", base_url=f"https://{HOST}", path=path, data=body, headers=headers)
	frappe.local.request = Request(env.get_environ())


@patch.dict(signing.PUBLIC_KEYS, {"test": PUB})
class TestApi(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.db.rollback)
		site = patch.object(frappe.local, "site", HOST)
		site.start()
		self.addCleanup(site.stop)

	def test_unsigned_is_forbidden(self):
		for method, fn in (("verify_owner", api.verify_owner), ("run_checks", api.run_checks)):
			with self.subTest(method=method):
				fake_request(method, {"email": "Administrator"}, signed=False)
				self.assertRaises(frappe.PermissionError, fn)

	# Regression: get_url() echoed the request host, so any Host passed the check (review S1, commit 50f1276).
	def test_host_check_ignores_site_config_host_name(self):
		fake_request("verify_owner", {"email": "Administrator"})
		with patch.object(frappe.local, "site", "other.m.frappe.cloud"):
			with patch.dict(frappe.conf, {"host_name": f"https://{HOST}"}):
				self.assertRaises(frappe.PermissionError, api.verify_owner)

	# Regression: a batch over MAX_CHECKS must get the same generic 403 as any bad body (commit 4a488e9).
	def test_bad_body_is_the_same_403(self):
		for method, fn, body in (
			("verify_owner", api.verify_owner, b"not json"),
			("verify_owner", api.verify_owner, [1]),
			("run_checks", api.run_checks, {"checks": "nope"}),
			("run_checks", api.run_checks, {}),
			("run_checks", api.run_checks, {"checks": [{"check_id": "a"}] * 301}),
		):
			with self.subTest(method=method, body=body):
				fake_request(method, body)
				self.assertRaises(frappe.PermissionError, fn)

	# Regression: Administrator (admin@example.com) passed verify_owner (commit 4a488e9).
	def test_verify_owner(self):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": "owner-probe@example.com",
				"first_name": "O",
				"roles": [{"role": "System Manager"}],
			}
		).insert()
		frappe.get_doc({"doctype": "User", "email": "plain-probe@example.com", "first_name": "P"}).insert()
		disabled = frappe.get_doc(
			{
				"doctype": "User",
				"email": "off-probe@example.com",
				"first_name": "D",
				"enabled": 0,
				"roles": [{"role": "System Manager"}],
			}
		).insert()
		profile = frappe.get_doc(
			{"doctype": "Role Profile", "role_profile": "probe-sysmgr", "roles": [{"role": "System Manager"}]}
		).insert()
		# Regression: on_update locks the profile for a queued job that never runs under a stubbed enqueue,
		# so the lock file outlived the rollback and reruns hit DocumentLockedError (probe from commit 4a488e9).
		self.addCleanup(profile.unlock)
		profile_user = {
			"doctype": "User",
			"email": "profile-probe@example.com",
			"first_name": "R",
			"role_profile_name": "probe-sysmgr",
		}
		if frappe.get_meta("User").has_field("role_profiles"):
			profile_user["role_profiles"] = [{"role_profile": "probe-sysmgr"}]
		frappe.get_doc(profile_user).insert()
		for email, ok in (
			("profile-probe@example.com", True),
			("admin@example.com", False),
			("owner-probe@example.com", True),
			("plain-probe@example.com", False),
			(disabled.email, False),
			("nobody@example.com", False),
			("", False),
			(5, False),
			(None, False),
		):
			with self.subTest(email=email):
				fake_request("verify_owner", {"email": email})
				self.assertEqual(api.verify_owner(), {"ok": ok})

	@patch("erpnext_assignment_checks.checks.run_checks", return_value=[{"check_id": "a", "found_count": 1}])
	def test_run_checks_signed(self, run):
		fake_request("run_checks", {"checks": [{"check_id": "a"}]})
		self.assertEqual(api.run_checks(), {"results": [{"check_id": "a", "found_count": 1}]})
		run.assert_called_once_with([{"check_id": "a"}])
