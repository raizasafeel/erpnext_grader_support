import json
import sys
from collections import defaultdict


def normalise(filters):
	if isinstance(filters, dict):
		return [[k, "=", v] for k, v in filters.items()]
	out = []
	for f in filters or []:
		if isinstance(f, list) and len(f) == 4 and f[0] == "Dynamic Link":
			out.append([f"links.{f[1]}", f[2], f[3]])
		elif isinstance(f, list) and f:
			out.append(f)
	return out


def fields_of(filters):
	return {f[0] for f in normalise(filters)}


def main(path):
	allowed = defaultdict(set)
	with open(path) as fh:  # nosemgrep: frappe-security-file-traversal
		rows = json.load(fh)
	for row in rows:
		for entries in json.loads(row.get("checks") or "{}").values():
			for entry in entries:
				dt = entry.get("doctype")
				if not dt:
					continue
				allowed[dt] |= {"name", "docstatus"} | fields_of(entry.get("filter"))
				for check in entry.get("checks", []):
					allowed[dt] |= fields_of(check.get("filter"))
					for item in check.get("fields_to_match") or []:
						allowed[dt] |= set(item) if isinstance(item, dict) else {item}
					table = check.get("table")
					for match in check.get("match") or []:
						allowed[dt] |= {f"{table}.{f}" for f in match} or {f"{table}.name"}
	print("ALLOWED: dict[str, frozenset[str]] = {")
	for dt in sorted(allowed):
		print(f"\t{json.dumps(dt)}: frozenset({json.dumps(sorted(allowed[dt]))}),")
	print("}")


if __name__ == "__main__":
	main(sys.argv[1])
