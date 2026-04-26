# Copyright (c) 2026, Raiza and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ERPNextGraderConnection(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		token: DF.Password | None
		token_expiry: DF.Datetime | None
	# end: auto-generated types

	pass
