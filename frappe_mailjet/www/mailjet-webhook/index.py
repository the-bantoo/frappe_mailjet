from frappe_mailjet.app import mailjet_webhook
import frappe

def get_context(context):
    
    #verifies if args contain a list of dicts or just one dict
    if frappe.form_dict.data:
        data = frappe.form_dict.data
        
        if data[0]['email'] != "" :
            mailjet_webhook(data)

    elif frappe.form_dict:
        data = frappe.form_dict

        args = []
        args.append(data)

        if data.email != "" :
            mailjet_webhook(args)

    return