from __future__ import annotations

import re
from typing import Any

import frappe

_DENIED_DOCTYPES = frozenset(
	{
		"User",
		"API Key",
		"Server Script",
		"Client Script",
		"Webhook",
		"Email Account",
		"Email Domain",
		"LDAP Settings",
		"Social Login Key",
		"System Settings",
		"Token Cache",
		"Integration Request",
		"OAuth Bearer Token",
		"OAuth Authorization Code",
		"OAuth Client",
		"OAuth Provider Settings",
		"Auth Provider",
		"Domain Settings",
		"File",
	}
)


def _doctype_allowed(doctype: str | None) -> bool:
	if not doctype:
		return False
	if doctype in _DENIED_DOCTYPES:
		return False
	# Block any doctype starting with "OAuth " or "Password " etc. just in case
	# a future Frappe release adds new sensitive ones with predictable prefixes.
	return not doctype.startswith(("OAuth ", "Password "))


def _norm(val: Any) -> str:
	return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", "", str(val or "").lower())).strip()


def _eq(a: Any, b: Any) -> bool:
	if isinstance(b, (int, float)) and not isinstance(b, bool):
		try:
			return float(a) == float(b)
		except (TypeError, ValueError):
			return False
	return _norm(a) == _norm(b)


def _contains(haystack: Any, needle: Any) -> bool:
	return _norm(needle) in _norm(haystack)


def _fmt(v: Any, *, quote: bool = False, none_text: str = "Not set") -> str:
	if v is None or v == "":
		return none_text
	if isinstance(v, bool):
		return "Yes" if v else "No"
	if isinstance(v, (list, tuple)):
		if not v:
			return none_text
		return ", ".join(_fmt(x, quote=quote, none_text=none_text) for x in v)
	if isinstance(v, dict):
		return ", ".join(
			f"{k}={_fmt(x, quote=quote, none_text=none_text)}" for k, x in v.items()
		)
	if quote and isinstance(v, str):
		return f'"{v}"'
	return str(v)


def _fmt_val(v: Any) -> str:
	"""Format a scalar for inline sentences — strings get quoted, None reads 'nothing'."""
	return _fmt(v, quote=True, none_text="nothing")


_OP_WORDS = {
	"=": "is",
	"==": "is",
	"!=": "is not",
	">": "is more than",
	">=": "is at least",
	"<": "is less than",
	"<=": "is at most",
	"in": "is one of",
	"not in": "is not any of",
	"like": "contains",
	"not like": "does not contain",
	"is": "is",
	"between": "is between",
}


def _humanize_filter(flt: Any) -> str:
	"""Render a Frappe filter as a readable English clause."""
	if not flt:
		return ""
	if isinstance(flt, dict):
		return " and ".join(f"{k} is {_fmt_val(v)}" for k, v in flt.items())
	if isinstance(flt, (list, tuple)):
		clauses: list[str] = []
		dyn: dict[str, tuple[str, Any]] = {}
		for item in flt:
			if not isinstance(item, (list, tuple)):
				continue
			if len(item) == 4:
				dt, field, op, val = item
				if dt == "Dynamic Link":
					dyn[field] = (op, val)
					continue
				clauses.append(f"{dt}.{field} {_OP_WORDS.get(op, op)} {_fmt_val(val)}")
			elif len(item) == 3:
				field, op, val = item
				clauses.append(f"{field} {_OP_WORDS.get(op, op)} {_fmt_val(val)}")
		if dyn:
			ld = dyn.get("link_doctype")
			ln = dyn.get("link_name")
			if ld and ln and ld[0] == "=" and ln[0] == "=":
				clauses.insert(0, f"linked to {ld[1]} {_fmt_val(ln[1])}")
			else:
				for field, (op, val) in dyn.items():
					clauses.append(
						f"Dynamic Link.{field} {_OP_WORDS.get(op, op)} {_fmt_val(val)}"
					)
		return " and ".join(clauses)
	return str(flt)


def _get_doc(doctype: str, name: str) -> dict | None:
	try:
		return frappe.get_doc(doctype, name).as_dict()
	except frappe.DoesNotExistError:
		return None
	except Exception:
		return None


def _get_list(doctype: str, filters=None, fields=None, limit=100) -> list[dict]:
	try:
		return frappe.get_all(
			doctype,
			filters=filters,
			fields=fields or ["name"],
			limit_page_length=limit,
		)
	except Exception:
		return []


def _res(
	check: dict,
	passed: bool,
	*,
	expected: Any = None,
	actual: Any = None,
) -> dict:
	return {
		"label": check.get("heading", ""),
		"passed": bool(passed),
		"expected": _fmt(expected) if expected is not None else "",
		"actual": _fmt(actual) if actual is not None else "",
	}


def _entry_label(entry: dict) -> str:
	name = entry.get("name")
	if isinstance(name, list):
		return " / ".join(str(n) for n in name)
	if name:
		return str(name)
	flt = entry.get("filter")
	return f"{entry['doctype']} matching {flt}" if flt else entry["doctype"]


# ── 4 check functions ────────────────────────────────────────


def _match(entry, doc, check):
	"""Doc fields match expected values. Reports the first mismatched field with
	its expected / actual value."""
	if not doc:
		return _res(
			check,
			False,
			expected=f"{entry['doctype']} '{_entry_label(entry)}'",
			actual="Document not found",
		)

	for pair in check.get("fields_to_match", []) or []:
		for field, expected in pair.items():
			actual = doc.get(field)
			options = expected if isinstance(expected, list) else [expected]
			if not any(_eq(actual, e) for e in options):
				return _res(
					check,
					False,
					expected=f"{field} is {_fmt_val(expected)}",
					actual=f"{field} is {_fmt_val(actual)}",
				)

	summary = ", ".join(
		f"{field} is {_fmt_val(val)}"
		for pair in check.get("fields_to_match", []) or []
		for field, val in pair.items()
	)
	return _res(check, True, expected=summary, actual=summary)


def _field_exists(entry, doc, check):
	"""Doc fields have non-empty values. Reports which fields were empty."""
	fields = check.get("fields_to_match", []) or []
	if not doc:
		return _res(
			check,
			False,
			expected=f"Non-empty: {', '.join(fields)}",
			actual="Document not found",
		)

	missing = [f for f in fields if not doc.get(f)]
	if missing:
		return _res(
			check,
			False,
			expected=f"Non-empty: {', '.join(fields)}",
			actual=f"Missing: {', '.join(missing)}",
		)
	return _res(
		check,
		True,
		expected=f"Non-empty: {', '.join(fields)}",
		actual="All set",
	)


def _exists_with_filter(entry, doc, check):
	"""At least one doc matches the filter."""
	rows = _get_list(entry["doctype"], filters=check["filter"], limit=check.get("limit", 100))
	clause = _humanize_filter(check["filter"])
	expected = (
		f"At least 1 {entry['doctype']} where {clause}"
		if clause
		else f"At least 1 {entry['doctype']}"
	)
	return _res(
		check,
		bool(rows),
		expected=expected,
		actual=f"{len(rows)} found",
	)


def _summarize_match(check: dict) -> str:
	parts = []
	for m in check.get("match", []) or []:
		parts.append(" and ".join(f"{f} is {_fmt_val(v)}" for f, v in m.items()))
	return "; ".join(parts) or "matching row"


def _check_rows(doc, check):
	rows = doc.get(check["table"]) or []
	for m in check["match"]:
		if not any(
			all(
				_contains(row.get(f), v) if isinstance(v, str) else _eq(row.get(f), v)
				for f, v in m.items()
			)
			for row in rows
		):
			return False
	return True


def _child_has_row(entry, doc, check):
	"""Child table has rows matching all conditions."""
	table = check.get("table", "rows")
	if doc and _check_rows(doc, check):
		return _res(
			check,
			True,
			expected=_summarize_match(check),
			actual=f"Found in {entry.get('doctype')} '{doc.get('name')}'.{table}",
		)

	flt = check.get("filter") or entry.get("filter")
	if flt:
		for p in _get_list(entry["doctype"], filters=flt, fields=["name"], limit=200):
			d = _get_doc(entry["doctype"], p["name"])
			if d and _check_rows(d, check):
				return _res(
					check,
					True,
					expected=_summarize_match(check),
					actual=f"Found in {entry['doctype']} '{p['name']}'.{table}",
				)

	return _res(
		check,
		False,
		expected=_summarize_match(check),
		actual="No matching row found"
		if doc
		else f"{entry['doctype']} '{_entry_label(entry)}' not found",
	)


_CHECKS = {
	"match": _match,
	"field_exists": _field_exists,
	"exists_with_filter": _exists_with_filter,
	"child_has_row": _child_has_row,
}


# ── runner ────────────────────────────────────────────────────


def _fetch_doc(entry):
	name = entry.get("name")
	if not name:
		flt = entry.get("filter")
		if flt:
			rows = _get_list(entry["doctype"], filters=flt, fields=["name"], limit=1)
			if rows:
				return _get_doc(entry["doctype"], rows[0]["name"])
		return None
	if isinstance(name, list):
		for n in name:
			doc = _get_doc(entry["doctype"], n)
			if doc:
				return doc
		return None
	return _get_doc(entry["doctype"], name)


def run_checks(checks: dict) -> dict:
	"""Evaluate a nested checks JSON against the local site."""
	results: list[dict] = []
	for section, entries in (checks or {}).items():
		for entry in entries or []:
			title = entry.get("title", "")
			if not _doctype_allowed(entry.get("doctype")):
				for check in entry.get("checks", []) or []:
					r = _res(
						check,
						False,
						expected="permitted doctype",
						actual=f"Doctype '{entry.get('doctype')}' is not allowed for grading.",
					)
					r["section"] = section
					r["title"] = title
					results.append(r)
				continue
			doc = _fetch_doc(entry)
			for check in entry.get("checks", []) or []:
				fn = _CHECKS.get(check.get("check_type"))
				if fn:
					r = fn(entry, doc, check)
				else:
					r = _res(
						check,
						False,
						expected=f"known check_type",
						actual=f"Unknown check_type '{check.get('check_type')}'",
					)
				r["section"] = section
				r["title"] = title
				results.append(r)

	total = len(results)
	passed = sum(1 for r in results if r["passed"])
	return {
		"total": total,
		"passed": passed,
		"percentage": round(passed / total * 100, 1) if total else 0,
		"results": results,
	}
