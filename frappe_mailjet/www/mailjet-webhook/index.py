from frappe_mailjet.app import mailjet_webhook, print_result, connect
import frappe

def get_context():
    
    #check if args contain a list of dicts or just one dict
    if frappe.form_dict.data:
        data = frappe.form_dict.data
        
        
        if data[0]['email'] != "" :
            mailjet_webhook(data)

    else:
        data = frappe.form_dict

        args = []
        args.append(data)

        if data.email != "" :
            mailjet_webhook(args)

    return

"""

{'event': 'sent',    'time': 1669384322, 'MessageID': 0, 'email': '', 'mj_campaign_id': 0, 'mj_contact_id': 0, 'customcampaign': '', 'mj_message_id': '', 'smtp_reply': '', 'CustomID': '', 'Payload': ''}

{'event': 'open',    'time': 1669384346, 'MessageID': 0, 'email': '', 'mj_campaign_id': 0, 'mj_contact_id': 0, 'customcampaign': '', 'CustomID': '', 'Payload': '', 'ip': '', 'geo': '', 'agent': ''}

{'event': 'click',   'time': 1669384364, 'MessageID': 0, 'email': '', 'mj_campaign_id': 0, 'mj_contact_id': 0, 'customcampaign': '', 'CustomID': '', 'Payload': '', 'url': '', 'ip': '', 'geo': '', 'agent': ''}

{'event': 'bounce',  'time': 1669384427, 'MessageID': 0, 'email': '', 'mj_campaign_id': 0, 'mj_contact_id': 0, 'customcampaign': '', 'CustomID': '', 'Payload': '', 'blocked': '', 'hard_bounce': '', 'error_related_to': '', 'error': ''}

{'event': 'spam',    'time': 1669384444, 'MessageID': 0, 'email': '', 'mj_campaign_id': 0, 'mj_contact_id': 0, 'customcampaign': '', 'CustomID': '', 'Payload': '', 'source': ''}

{'event': 'blocked', 'time': 1669384457, 'MessageID': 0, 'email': '', 'mj_campaign_id': 0, 'mj_contact_id': 0, 'customcampaign': '', 'CustomID': '', 'Payload': '', 'error_related_to': '', 'error': ''}

{'event': 'unsub',   'time': 1669384484, 'MessageID': 0, 'email': '', 'mj_campaign_id': 0, 'mj_contact_id': 0, 'customcampaign': '', 'CustomID': '', 'Payload': '', 'mj_list_id': '', 'ip': '', 'geo': '', 'agent': ''}



{'event': 'unsub', 'time': 1669387932, 'MessageID': 94012642276192743, 'Message_GUID': 'df8e2b34-c9aa-4c58-80bd-a2418c18f652', 'email': 'adam.daveed@gmail.com', 
 'mj_campaign_id': 7653742672, 'mj_contact_id': 2847931267, 'customcampaign': 'mj.nl=10400513', 'mj_list_id': 10212675, 'ip': '165.56.185.124', 'geo': 'ZM', 
 'agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36', 'CustomID': '', 'Payload': ''}

{'event': 'unsub', 'time': 1669396859, 'MessageID': 94012642276192743, 'Message_GUID': 'df8e2b34-c9aa-4c58-80bd-a2418c18f652', 'email': 'adam.daveed@gmail.com', 
 'mj_campaign_id': 7653742672, 'mj_contact_id': 2847931267, 'customcampaign': 'mj.nl=10400513', 'mj_list_id': 10212675, 'ip': '165.56.185.124', 'geo': 'ZM', 
 'agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36', 'CustomID': '', 'Payload': ''}


sent    - MessageID, email, mj_campaign_id, mj_contact_id, Payload
open    - MessageID, email, mj_campaign_id, mj_contact_id, Payload, geo
click   - MessageID, email, mj_campaign_id, mj_contact_id, Payload, geo, url
bounce  - MessageID, email, mj_campaign_id, mj_contact_id, Payload, geo, url, blocked, hard_bounce, error_related_to, error
spam    - MessageID, email, mj_campaign_id, mj_contact_id, Payload, source
blocked - MessageID, email, mj_campaign_id, mj_contact_id, Payload, error_related_to, error
unsub   - MessageID, email, mj_campaign_id, mj_contact_id, Payload, mj_list_id, geo

event name = get_list = mj_campaign_id


"""