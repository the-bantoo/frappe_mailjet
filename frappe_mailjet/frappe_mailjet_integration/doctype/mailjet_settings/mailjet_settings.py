# Copyright (c) 2022, Bantoo and contributors
# For license information, please see license.txt

from frappe import _
import frappe
from frappe.model.document import Document

class MailjetSettings(Document):
	def validate(self):
		
		# check for duplicate fields and inform the user

		fields = []
		for field in self.custom_fields:
			if field.field_name in fields:
				frappe.msgprint(
					_("The field <strong>{1}</strong> at row {0} is a duplicate.").format(field.idx, field.field_name),
					raise_exception=1,
					indicator="red",
				)
			else:
				fields.append(field.field_name)

@frappe.whitelist(allow_guest=True)
def get_doc_fields(doc):
	"""returns a list of fields from a doc"""
	doc = frappe.get_meta(doc)

	return [d.fieldname for d in doc.fields if d.fieldtype in ("HTML", "Read Only", "Code", "Data", "Text Editor", "Time", "Small Text", "Text", "Text Editor", "Text", "Small Text", "Read Only", "Select", "Link", "Int", "Float", "Check", "Date", "Datetime", "Phone", "Duration")]
