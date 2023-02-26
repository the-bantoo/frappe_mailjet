// Copyright (c) 2022, Bantoo and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mailjet Settings', {
	refresh: function(frm) {
		if (frm.doc.for_doctype){
			frappe.call({
				method: "frappe_mailjet.frappe_mailjet_integration.doctype.mailjet_settings.mailjet_settings.get_doc_fields",
				args: {
					"doc": frm.doc.for_doctype
				},
				callback: function(r) {
					frm.fields_dict.custom_fields.grid.update_docfield_property("field_name","options", r.message);
				}
			});
		}
		
		/**
		frappe.call({
			method: "frappe_mailjet.app.sync",
			callback: function(r) {
				console.log(r.message)
			}
		})
		*/
	},
	after_save: function(frm) {
		frappe.call({
			method: "frappe_mailjet.app.initialise",
			callback: function(r) {
				//console.log(r.message)
			}
		});
		//cur_frm.refresh_field("custom_fields");
		frm.refresh_field("custom_fields");
		//frm.reload_doc()
	}
});