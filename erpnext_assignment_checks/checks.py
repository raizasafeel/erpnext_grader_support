import time

import frappe
from frappe import _
from frappe.utils import compare

from erpnext_assignment_checks import allowlist

CAP = 1000
MAX_CHECKS = 300
TIME_BUDGET_SECONDS = 20
OPERATORS = {"=", "!=", "like", "not like", "in", "not in", ">", "<", ">=", "<=", "is"}
SCALARS = (str, int, float)


class CheckError(Exception):
	def __init__(self, code: str):
		self.code = code


def run_checks(checks: list) -> list[dict]:
	if not isinstance(checks, list) or len(checks) > MAX_CHECKS:
		frappe.throw(_("Too many checks"), frappe.ValidationError)
	deadline = time.monotonic() + TIME_BUDGET_SECONDS
	results = []
	for check in checks:
		check_id = str(check.get("check_id") or "") if isinstance(check, dict) else ""
		if time.monotonic() > deadline:
			results.append({"check_id": check_id, "error": "timeout"})
			continue
		try:
			results.append({"check_id": check_id, "found_count": _count(check)})
		except CheckError as e:
			results.append({"check_id": check_id, "error": e.code})
	return results


def _count(check: dict) -> int:
	doctype = check.get("target_doctype")
	filters = check.get("filters")
	if not isinstance(doctype, str) or not isinstance(filters, list):
		raise CheckError("invalid")
	allowed = allowlist.ALLOWED.get(doctype)
	if allowed is None:
		raise CheckError("not_allowed")
	for f in filters:
		_validate_filter(f, allowed)
	meta = frappe.get_meta(doctype)
	if meta.issingle:
		return _count_single(doctype, filters)
	try:
		names = frappe.get_all(
			doctype, filters=_to_frappe_filters(meta, filters), pluck="name", distinct=True, limit=CAP + 1
		)
	except Exception:
		raise CheckError("invalid")
	return min(len(names), CAP)


def _validate_filter(f, allowed: frozenset) -> None:
	if not (isinstance(f, list) and len(f) == 3 and isinstance(f[0], str) and f[1] in OPERATORS):
		raise CheckError("invalid")
	field, op, value = f
	if op == "is":
		if value not in ("set", "not set"):
			raise CheckError("invalid")
	elif op in ("in", "not in"):
		if not (isinstance(value, list) and all(isinstance(v, SCALARS) for v in value)):
			raise CheckError("invalid")
	elif not isinstance(value, SCALARS):
		raise CheckError("invalid")
	if field not in allowed:
		raise CheckError("not_allowed")


def _to_frappe_filters(meta, filters: list) -> list:
	out = []
	for field, op, value in filters:
		if "." not in field:
			out.append([meta.name, field, op, value])
			continue
		table, child_field = field.split(".", 1)
		df = meta.get_field(table)
		if not df or df.fieldtype not in ("Table", "Table MultiSelect"):
			raise CheckError("invalid")
		out.append([df.options, child_field, op, value])
	return out


def _count_single(doctype: str, filters: list) -> int:
	if any("." in f[0] for f in filters):
		raise CheckError("invalid")
	doc = frappe.get_single(doctype)
	return int(all(compare(doc.get(field), op, value) for field, op, value in filters))
