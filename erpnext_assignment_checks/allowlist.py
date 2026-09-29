"""Doctypes and fields the grader may count. Child fields are "table.field"."""

ALLOWED: dict[str, frozenset[str]] = {
	"Account": frozenset(["docstatus", "name"]),
	"Accounting Dimension": frozenset(["docstatus", "document_type", "name"]),
	"Address": frozenset(["address_type", "docstatus", "links.link_doctype", "links.link_name", "name"]),
	"BOM": frozenset(["docstatus", "is_active", "is_default", "items.name", "name"]),
	"Branch": frozenset(["docstatus", "name"]),
	"Budget": frozenset(
		[
			"accounts.account",
			"accounts.budget_amount",
			"action_if_annual_budget_exceeded",
			"action_if_monthly_budget_exceeded",
			"company",
			"docstatus",
			"name",
		]
	),
	"Company": frozenset(
		["abbr", "chart_of_accounts", "cost_center", "country", "default_currency", "docstatus", "name"]
	),
	"Contact": frozenset(["docstatus", "links.link_doctype", "links.link_name", "name"]),
	"Cost Center": frozenset(["docstatus", "name", "parent_cost_center"]),
	"Customer": frozenset(
		["customer_group", "customer_type", "default_currency", "docstatus", "name", "territory"]
	),
	"Delivery Note": frozenset(["customer", "docstatus", "items.item_code", "items.qty", "name"]),
	"Fiscal Year": frozenset(["docstatus", "name"]),
	"Item": frozenset(
		["docstatus", "is_stock_item", "item_group", "item_name", "name", "stock_uom", "valuation_method"]
	),
	"Item Price": frozenset(
		["buying", "docstatus", "item_code", "name", "price_list", "price_list_rate", "selling"]
	),
	"Journal Entry": frozenset(
		[
			"accounts.account",
			"accounts.credit_in_account_currency",
			"accounts.debit_in_account_currency",
			"company",
			"docstatus",
			"name",
		]
	),
	"Payment Entry": frozenset(["docstatus", "name", "party", "payment_type"]),
	"Purchase Invoice": frozenset(
		["branch", "docstatus", "items.item_code", "items.qty", "name", "supplier"]
	),
	"Purchase Order": frozenset(["docstatus", "items.item_code", "items.qty", "name", "supplier"]),
	"Purchase Receipt": frozenset(["docstatus", "items.item_code", "items.qty", "name", "supplier"]),
	"Role Profile": frozenset(["docstatus", "name"]),
	"Sales Invoice": frozenset(["branch", "customer", "docstatus", "items.item_code", "items.qty", "name"]),
	"Sales Order": frozenset(["customer", "docstatus", "items.item_code", "items.qty", "name"]),
	"Stock Entry": frozenset(["docstatus", "items.qty", "name", "stock_entry_type"]),
	"Stock Settings": frozenset(["default_warehouse", "docstatus", "name"]),
	"Supplier": frozenset(["country", "default_currency", "docstatus", "name", "supplier_group"]),
	"User": frozenset(["docstatus", "full_name", "name", "role_profile_name"]),
	"Warehouse": frozenset(["docstatus", "name", "parent_warehouse"]),
}
