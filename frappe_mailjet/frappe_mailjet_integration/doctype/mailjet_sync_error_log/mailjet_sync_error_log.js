// Copyright (c) 2024, Bantoo and contributors
// For license information, please see license.txt
var not_confirmed = true;


frappe.ui.form.on('Mailjet Sync Error Log', {
    refresh(frm) {
        not_confirmed = true;

        if (frm.doc.total !== frm.doc.contacts.length){
            frm.set_value('total', frm.doc.contacts.length);
            frm.refresh();
        }
        frm.events.delete_mode(frm);
    },
    delete_mode: function(frm) {
        if (frm.doc.delete_mode === 1){
            frm.set_df_property('contacts', 'cannot_delete_rows', 0);
        }
        else{
            frm.set_df_property('contacts', 'cannot_delete_rows', 1);
        }
    },
    delete_contact: function(frm, cdt, cdn) {
        // Get the name of the Email Group Member to delete
        let row = locals[cdt][cdn];
        let contact_name = row.contact;

        // Confirm before deletion
        frappe.confirm(
            'Are you sure you want to delete this contact?',
            function() {
                if(!contact_name){
                    cur_frm.get_field("contacts").grid.grid_rows[row.idx-1].remove();
                    frm.refresh();
                }
                // Call the server method
                frappe.call({
                    method: 'frappe_mailjet.app.delete_email_group_member',
                    args: {
                        'contact_name': contact_name 
                    },
                    callback: function(r) {                     
                        cur_frm.get_field("contacts").grid.grid_rows[row.idx-1].remove();
                        // frappe.db.delete_doc('MJ Log Contacts', cdn);
                        frm.set_value('total', doc.contacts.length || 0);
                        
                        frm.refresh();
                    
                    }
                });
            }
        );
    }
});



frappe.ui.form.on('MJ Log Contacts', {
    delete: function(frm, cdt, cdn) {
        // del button in table
        frm.events.delete_contact(frm, cdt, cdn);
    },
    before_contacts_remove: (frm, cdt, cdn) => {
        let row = locals[cdt][cdn];
        let contact_name = row.contact;

        if(!contact_name){
            return;
        }

        // Call the server method
        frappe.call({
            method: 'frappe_mailjet.app.delete_email_group_member',
            args: {
                'contact_name': contact_name
            },
            callback: function(r) {
                if (r.message == 'done') {
                    frappe.db.delete_doc('MJ Log Contacts', cdn);
                }
            }
        });
    },
    contacts_remove: (frm, cdt, cdn) => {                
        frm.set_value('total', frm.doc.contacts.length);
        frm.reload_doc();
    }
    
});