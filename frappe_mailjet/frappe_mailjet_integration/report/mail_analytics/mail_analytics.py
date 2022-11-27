# Copyright (c) 2022, Bantoo and contributors
# For license information, please see license.txt


import frappe
from frappe import _

from mailjet_rest import Client
import os

def execute(filters=None):
    
    mailjet = connect()
    list_id = '7653742604'
    list_id_wds = '10212675'
    contact = '2851198213'
    """
    #result = mailjet.contactstatistics.get(id='2851198213') #ContactsList=id)
    result =mailjet.contactdata.get(filters={
            'contact': contact
        }) #mailjet.contact.get(id=contact)
        
    
    result = mailjet.contactstatistics.get(
        filters={
            'contact': contact
        })
    
    result = mailjet.statcounters.get(filters={
        'CounterSource':'List',
        'CounterTiming': 'Message',
        'CounterResolution':'Lifetime',
        'SourceID': list_id_wds + ',' + list_id
        })

    #gets stats for all contacts who've been emailed
    result = mailjet.contactstatistics.get(
        filters={
            #'contact': contact
        })

    {
        'BlockedCount': 0, 
        'BouncedCount': 0, 
        'ClickedCount': 0, 
        'ContactID': 2847931231, 
        'DeferredCount': 0, 
        'DeliveredCount': 6, 
        'HardBouncedCount': 0, 
        'LastActivityAt': '2022-11-24T12:09:30Z', 
        'MarketingContacts': 0, 'OpenedCount': 1, 
        'PreQueuedCount': 6, 'ProcessedCount': 6, 
        'QueuedCount': 6, 'SoftBouncedCount': 0, 
        'SpamComplaintCount': 0, 'UnsubscribedCount': 0, 
        'UserMarketingContacts': 0, 
        'WorkFlowExitedCount': 0
    }
    """

    #frappe.errprint("report")
    print_result(result)
    return get_columns(), get_data(filters)

def get_data(filters):
    data = frappe.db.sql("""SELECT c.user, c.sender, c.recipients, c.subject, c.read_by_recipient, e.creation, e.original_url, e.clicked, e.click_rate FROM `tabEmail Links` e INNER JOIN `tabCommunication` c ON e.parent = c.name;""")
    return data

def get_columns():
    return [
        "User Name: Data",
        "Sender Email: Data",
        "Recipient: Data",
        "Subject: Data",
        "Seen: Check",
        "Date: Date",
          "Link: Data",
        "Clicked: Check",
        "Click Rate: Int",
    ]


def print_result(result):

    if result:
        frappe.errprint(result.status_code)
    if result.json():
        frappe.errprint(result.json())

    return
          
def get_credentials(doc=None):
    """get api key and secret from the app settings doctype"""
    
    if doc:
        creds = doc
    else:
        creds = frappe.get_doc("Mailjet Settings")
    
    return {'key': creds.api_key, 'secret': creds.get_password('secret_key') }

def test_connection(creds):
    mailjet = Client(auth=(creds['key'], creds['secret']), version='v3')
    filters = {
        'Limit': 1
    }
    result = mailjet.contact.get(filters=filters)
    return { 'code' : result.status_code, 'res': result, 'connection': mailjet }

def connect():
    """returns a connection or throws error if cannot connect"""
    res = test_connection(get_credentials())

    if res['code'] != 200:
        frappe.throw("Mailjet credentials might be incorrect")
    else:
        return res['connection']
