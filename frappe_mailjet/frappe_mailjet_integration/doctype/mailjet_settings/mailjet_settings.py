# Copyright (c) 2022, Bantoo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class MailjetSettings(Document):
	pass

@frappe.whitelist(allow_guest=True)
def get_doc_fields(doc):
	"""returns a list of fields from a doc"""
	doc = frappe.get_meta(doc)

	return [d.fieldname for d in doc.fields if d.fieldtype in ("HTML", "Read Only", "Code", "Data", "Text Editor", "Time", "Small Text", "Text", "Text Editor", "Text", "Small Text", "Read Only", "Select", "Link", "Int", "Float", "Check", "Date", "Datetime", "Phone", "Duration")]
