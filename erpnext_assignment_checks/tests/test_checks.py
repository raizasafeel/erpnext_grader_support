from unittest.mock import patch

import frappe

try:
	from frappe.tests import IntegrationTestCase
except ImportError:
	from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from erpnext_assignment_checks import checks

ALLOW = {
	"ToDo": frozenset({"name", "description", "status"}),
	"User": frozenset({"name", "enabled", "roles.role"}),
	"System Settings": frozenset({"country"}),
}


@patch.dict("erpnext_assignment_checks.allowlist.ALLOWED", ALLOW, clear=True)
class TestRunChecks(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.db.rollback)
		for i in range(3):
			frappe.get_doc({"doctype": "ToDo", "description": f"grader-probe {i}"}).insert()

	def run1(self, check):
		return checks.run_checks([check])[0]

	def test_counts_matching_rows(self):
		r = self.run1({"check_id": "a", "target_doctype": "ToDo", "filters": [["description", "like", "grader-probe%"]]})
		self.assertEqual(r, {"check_id": "a", "found_count": 3})

	def test_output_has_no_values(self):
		r = self.run1({"check_id": "a", "target_doctype": "ToDo", "filters": []})
		self.assertEqual(set(r), {"check_id", "found_count"})
		self.assertIsInstance(r["found_count"], int)

	def test_not_allowed_doctype_and_field(self):
		for check in (
			{"check_id": "a", "target_doctype": "Communication", "filters": []},
			{"check_id": "a", "target_doctype": "ToDo", "filters": [["owner", "=", "x"]]},
			{"check_id": "a", "target_doctype": "User", "filters": [["roles.parent", "=", "x"]]},
		):
			with self.subTest(check=check):
				self.assertEqual(self.run1(check), {"check_id": "a", "error": "not_allowed"})

	def test_invalid_shapes(self):
		for filters in (
			"nope",
			[["description"]],
			[["description", "regexp", "x"]],
			[["description", "is", "maybe"]],
			[["description", "in", "not-a-list"]],
			[["description", "=", {"a": 1}]],
		):
			with self.subTest(filters=filters):
				r = self.run1({"check_id": "a", "target_doctype": "ToDo", "filters": filters})
				self.assertEqual(r, {"check_id": "a", "error": "invalid"})

	def test_child_filters_match_same_row(self):
		user = frappe.get_doc({"doctype": "User", "email": "grader-probe@example.com", "first_name": "P",
			"roles": [{"role": "Auditor"}, {"role": "Translator"}]}).insert()
		same_row = [["name", "=", user.name], ["roles.role", "=", "Auditor"], ["roles.role", "=", "Translator"]]
		r = self.run1({"check_id": "a", "target_doctype": "User", "filters": same_row})
		self.assertEqual(r["found_count"], 0)
		one = [["name", "=", user.name], ["roles.role", "=", "Auditor"]]
		self.assertEqual(self.run1({"check_id": "a", "target_doctype": "User", "filters": one})["found_count"], 1)

	def test_single_doctype(self):
		frappe.db.set_single_value("System Settings", "country", "India")
		country = "India"
		yes = self.run1({"check_id": "a", "target_doctype": "System Settings", "filters": [["country", "=", country]]})
		no = self.run1({"check_id": "a", "target_doctype": "System Settings", "filters": [["country", "=", "Atlantis"]]})
		self.assertEqual((yes["found_count"], no["found_count"]), (1, 0))

	@patch.object(checks, "CAP", 2)
	def test_count_is_capped(self):
		self.assertEqual(self.run1({"check_id": "a", "target_doctype": "ToDo", "filters": [["description", "like", "grader-probe%"]]})["found_count"], 2)

	def test_too_many_checks_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			checks.run_checks([{"check_id": str(i), "target_doctype": "ToDo", "filters": []} for i in range(301)])

	def test_time_budget(self):
		with patch.object(checks, "time") as clock:
			clock.monotonic.side_effect = [0, 0, 100, 100]
			out = checks.run_checks([{"check_id": "a", "target_doctype": "ToDo", "filters": []},
				{"check_id": "b", "target_doctype": "ToDo", "filters": []}])
		self.assertEqual(out[1], {"check_id": "b", "error": "timeout"})
