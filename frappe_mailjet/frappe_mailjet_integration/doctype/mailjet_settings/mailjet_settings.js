// Copyright (c) 2022, Bantoo and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mailjet Settings', {
	refresh: function(frm) {
		/**
		frappe.call({
			method: "frappe_mailjet.app.sync",
			callback: function(r) {
				console.log(r.message)
			}
		})
		*/
		frappe.call({
			method: "frappe_mailjet.app.sync",
			callback: function(r) {
				console.log(r.message)
			}
		})
	},
	after_save: function(frm) {
		frappe.call({
			method: "frappe_mailjet.app.initialise",
			callback: function(r) {
				console.log(r.message)
			}
		});
		//cur_frm.refresh_field("custom_fields");
		frm.refresh_field("custom_fields");
		frm.reload_doc()
	}
});
