from frappe_mailjet.app import mailjet_webhook
import frappe

def get_context(context):
    
    #verifies if args contain a list of dicts or just one dict
    if frappe.form_dict.data:
        data = frappe.form_dict.data
        
        if data[0]['email'] != "" :
            frappe.errprint(11)
            mailjet_webhook(data)

        frappe.errprint(data)
        frappe.errprint(1)

    elif frappe.form_dict:
        d = frappe.form_dict

        data = []
        data.append(d)
        if d.email != "" :
            frappe.errprint(22)
            mailjet_webhook(data)
        
        frappe.errprint(data)
        frappe.errprint(2)

    else:
        frappe.errprint('no data in payload')

    return