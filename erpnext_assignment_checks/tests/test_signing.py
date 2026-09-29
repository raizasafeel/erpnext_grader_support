import hashlib
from unittest.mock import patch

try:
	from frappe.tests import IntegrationTestCase
except ImportError:
	from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from erpnext_assignment_checks import signing

TEST_KEY_ID = "test"
TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAA6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg=
-----END PUBLIC KEY-----
"""
HOST = "trial.m.frappe.cloud"
PATH = "/api/method/erpnext_assignment_checks.api.verify_owner"
BODY = b'{"email":"student@example.com"}'
TS = "1790000000"
SIG = "hXHFnB5WH6S4n4fk9ZigERhOU5XIFeGiI2YQMEnfYrQvyR8b/kesUEQ0D5XqSjKRTXfeU0JaEt+dI2veNda5BA=="


def headers(**over):
	h = {"X-Grader-Key-Id": TEST_KEY_ID, "X-Grader-Timestamp": TS, "X-Grader-Signature": SIG}
	h.update(over)
	return h


@patch.dict(signing.PUBLIC_KEYS, {TEST_KEY_ID: TEST_PUBLIC_KEY})
class TestSigning(IntegrationTestCase):
	def test_message_format(self):
		expected = f"{HOST}\n{TS}\n{PATH}\n{hashlib.sha256(BODY).hexdigest()}".encode()
		self.assertEqual(signing.signing_message(HOST, TS, PATH, BODY), expected)

	def test_valid_vector(self):
		self.assertTrue(signing.verify(headers(), HOST, PATH, BODY, now=int(TS)))

	def test_rejects(self):
		cases = {
			"tampered body": (headers(), HOST, PATH, b'{"email":"x@example.com"}', int(TS)),
			"other host": (headers(), "other.m.frappe.cloud", PATH, BODY, int(TS)),
			"other path": (headers(), HOST, "/api/method/x", BODY, int(TS)),
			"stale": (headers(), HOST, PATH, BODY, int(TS) + 301),
			"future": (headers(), HOST, PATH, BODY, int(TS) - 301),
			"unknown key": (headers(**{"X-Grader-Key-Id": "nope"}), HOST, PATH, BODY, int(TS)),
			"missing sig": (headers(**{"X-Grader-Signature": ""}), HOST, PATH, BODY, int(TS)),
			"garbage sig": (headers(**{"X-Grader-Signature": "!!"}), HOST, PATH, BODY, int(TS)),
			"non-numeric ts": (headers(**{"X-Grader-Timestamp": "1e9"}), HOST, PATH, BODY, int(TS)),
			"unicode digit ts": (headers(**{"X-Grader-Timestamp": "\u00b2"}), HOST, PATH, BODY, int(TS)),
			"overlong ts": (headers(**{"X-Grader-Timestamp": "9" * 5000}), HOST, PATH, BODY, int(TS)),
			"oversized": (headers(), HOST, PATH, b"x" * (256 * 1024 + 1), int(TS)),
		}
		for label, args in cases.items():
			with self.subTest(label):
				self.assertFalse(signing.verify(*args[:4], now=args[4]))
