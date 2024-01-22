import frappe
from frappe import _, exceptions
import subprocess
import sys
import time
import json
from datetime import datetime, timedelta


def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    frappe.errprint(package + " has been installed")

try:
    import mailjet_rest
except:
    # ModuleNotFoundError
    install("mailjet_rest")

from mailjet_rest import Client

@frappe.whitelist()
def update_subs():
    """updates the total_subscribers in Email Group"""

    groups = frappe.get_all('Email Group', fields=['name', 'total_subscribers'], limit=0)
    for group in groups:
        update_total_subscribers(group)
    
    frappe.msgprint('Updated Total Subscribers for all Email Groups')

def update_total_subscribers(group):
    actual_subs = get_total_subscribers(group)

    if actual_subs != group.get('total_subscribers'):        
        frappe.db.set_value('Email Group', group.get('name'), 'total_subscribers', actual_subs)
        frappe.db.commit()

def get_total_subscribers(group):
    return frappe.db.sql(
        """select count(*) from `tabEmail Group Member`
        where email_group=%s""",
        group.get('name'),
    )[0][0]


def get_credentials(doc=None):
    """get api key and secret from the app settings doctype"""
    
    if doc:
        creds = doc
    else:
        creds = frappe.get_doc("Mailjet Settings")
    
    return {'key': creds.api_key, 'secret': creds.get_password('secret_key') }


@frappe.whitelist()
def verify_credentials(doc, method=None):
    """verify if user provided credentials are correct after update"""
    creds = get_credentials(doc)
    res = test_connection(creds)

    if res['code'] != 200:
        frappe.msgprint(msg=_("Double check your credentials"), title=_("Oh no..."), indicator="orange")
    else:
        frappe.msgprint(msg=_("You're connected to Mailjet"), title=_("Yey!"), indicator="green")


def test_connection(creds):
    mailjet = Client(auth=(creds['key'], creds['secret']))
    filters = {
        'Limit': 1
    }
    result = mailjet.contact.get(filters=filters)
    return { 'code' : result.status_code, 'res': result, 'connection': mailjet }

@frappe.whitelist()
def force_sync():
    # frappe.msgprint(_("Sync started in the background."))
    sync()
    frappe.msgprint(_("Manual sync is complete."))
    
def sync():
    try:
        print('mailjet sync ------ start')        
        connection = connect()

        sync_contact_lists(connection)
        sync_contacts(connection)
        sync_campaigns(connection)

        print('maijet sync ------ complete')
    except Exception as e:
        print(e)


def chunked_data(data, size):
    """Yield successive size chunks from data."""
    for i in range(0, len(data), size):
        yield data[i:i + size]

@frappe.whitelist()
def delete_email_group_member(contact_name):
    try:
        # Delete the Email Group Member document
        frappe.delete_doc('Email Group Member', contact_name)
        
        # frappe.errprint('delete -----------------------------> ' + contact_name)
        # log = frappe.get_doc('Mailjet Sync Error Log', log_name)
        # log.total = len(log.contacts) - 1
        # log.save()
        # frappe.db.commit()
        
        return 'done'
    except Exception as e:
        frappe.throw(str(e))

@frappe.whitelist()
def delete_multiple_email_group_members(contact_names):
    try:
        s = contact_names
        s = s.replace('"contacts"', '').replace(':', '').replace('{[', '').replace(']}', '')
        contacts = s.split(",")

        for c in contacts:
            delete_email_group_member(c)

    except Exception as e:
        frappe.throw(str(e))

def sync_contacts(mailjet):
    """Sync all Email Group Members to mailjet as contacts"""

    list_result = mailjet.contactslist.get(filters={'limit': 0})

    if list_result.status_code in [200, 201]:
        contact_list = list_result.json()['Data']
        all_contact_lists = frappe.get_all('Email Group', fields=['name', 'mailjet_id'], limit=0)

        for cl in contact_list:
            _contact_list = cl['Name']
            # _contact_list = 'World Data Summit All'
            
            contacts = frappe.db.get_all('Email Group Member', fields={'name', 'email', 'mailjet_id', 'unsubscribed'}, limit=0, filters={
                'email_group': _contact_list #, 'name': 'EGM7208'
            })

            if contacts:
                sub_data = []
                unsub_data = []
                not_synched = []

                for contact in contacts:
                    properties = get_contact_properties(contact.email)
                    if not properties:
                        not_synched.append(contact)
                        continue
                    properties = properties[0]

                    full_name = f"{properties.get('first_name', '')} {properties.get('last_name', '')}".strip()
                    contact_data = {
                        'Email': contact.email,
                        "Name": full_name,
                        "IsExcludedFromCampaigns": "false",
                        "Properties": properties
                    }

                    if contact.unsubscribed == 0:
                        sub_data.append(contact_data)
                    else:
                        unsub_data.append(contact_data)

                contactlist_id = get_dict_by_value(all_contact_lists, 'name', _contact_list)['mailjet_id']

                for data_chunk in chunked_data(sub_data, 1000):
                    result = mailjet.contactslist_managemanycontacts.create(id=contactlist_id, data={
                        'Action': "addforce",
                        'Contacts': data_chunk
                    })
                    # Handle result or log it

                for data_chunk in chunked_data(unsub_data, 1000):
                    result = mailjet.contactslist_managemanycontacts.create(id=contactlist_id, data={
                        'Action': "unsub",
                        'Contacts': data_chunk
                    })
                    # Handle result or log it

                update_contacts_by_list(_contact_list, contactlist_id, contacts, not_synched, mailjet)
                create_sync_error_log(not_synched, _contact_list, 'Unavailable Lead or Request', '', 'Ongoing')
                #print_result(result)  # Uncomment if needed

def create_sync_error_log(not_synched, contact_list, reason, next_action, status):
    """
    Create a log entry in 'Mailjet Sync Error Log' if not_synched list is different from today's earlier log,
    and if the last matching log does not have 'stop_future_logs' set to 1.
    """

    total_not_synched = len(not_synched)
    if not total_not_synched or total_not_synched < 1:
        return

    today = datetime.now()
    start_of_day = datetime(today.year, today.month, today.day)

    # Convert not_synched list to a JSON string for comparison
    not_synched_json = json.dumps(not_synched, sort_keys=True)

    identical_log_exists = frappe.get_all('Mailjet Sync Error Log', 
        fields=['name'],
        order_by='creation desc',
        limit=1,
        filters={
            'total': total_not_synched,
            'contact_list': contact_list
    })

    if identical_log_exists:
        return

    # Create a new log entry
    log_entry = frappe.get_doc({
        'doctype': 'Mailjet Sync Error Log',
        'contact_list': contact_list,
        'reason': reason,
        'next_action': next_action,
        'status': status,
        'total': total_not_synched,
        'contacts': []  # Child table field
    })

    # Add not_synched contacts to the child table
    for contact in not_synched:
        log_entry.append('contacts', {
            'contact': contact['name'],
            'email': contact['email'],
            'contact_list': contact_list,
            'is_unsubscribed': contact['unsubscribed']
        })

    log_entry.insert()
    frappe.db.commit()
    


def update_contacts_by_list(contact_list, contactlist_id=None, members=None, not_synched=[], mailjet=None):
    """Get IDs and updated time"""

    if not mailjet:
        mailjet = connect()
    
    if not members:
        members = frappe.db.get_all('Email Group Member', fields={'name', 'email', 'mailjet_id', 'unsubscribed'}, limit=0, filters={
                'email_group': contact_list
            })
    all_contacts = []
    offset = 0
    limit = 1000  # Adjust if needed

    # bypass api limit to retrieve all MJ records
    while True:
        result = mailjet.contact.get(filters={
            'Limit': limit,
            'Offset': offset,
            'ContactsList': contactlist_id,
        })

        if result.status_code not in [200, 201]:
            break

        data = result.json().get('Data', [])
        if not data:
            break

        all_contacts.extend(data)
        offset += limit

    #print_result(result)
    # frappe.errprint('list: ' + contact_list)
    # frappe.errprint("erp count: " + str(len(members)))
    # frappe.errprint("mj count: " + str(len(all_contacts)))
    # frappe.errprint("not synched count: " + str(len(not_synched)))
    # frappe.errprint(not_synched)

    if int(result.status_code) in [200, 201]:

        #frappe.errprint(result.json()['Data'])

        member_emails = []
        for m in members:
            member_emails.append(m.email.lower())

        
        
        for contact in all_contacts:
            email = contact.get('Email', None)
            
            if email and email in member_emails:
                email = email.lower()
                member = get_dict_by_value(members, 'email', email)

                # true if subscription status is different
                update_subscription_status = ( (contact['UnsubscribedBy'] != "") and (member['unsubcribed'] == 0) )
                if (str(contact['ID']) != str(member['mailjet_id']) ) or update_subscription_status:
                    """only update records if they have a de-similar IDs or difference in subscription status"""
                    # frappe.errprint(str(contact['ID']) + "MJ | ERP "+  str(member['mailjet_id']) )

                    doc = frappe.get_doc( "Email Group Member", member['name'] )
                    
                    doc.last_update = contact['LastUpdateAt']
                    doc.mailjet_id = contact['ID']

                    if update_subscription_status:
                        doc.unsubcribed = 1
                    doc.save( ignore_permissions=True, ignore_version=True )

def get_dict_by_value(dict_list, field, value):
    """returns dictionary with specific value in given field"""
    for d in dict_list:
        if d.get(field).lower() == value.lower():
            return d

import inspect

def print_result(result):
    # frappe.errprint("Source: " + inspect.stack()[1][3])


    if result:
        frappe.errprint(result.status_code)
    if result.json():
        frappe.errprint(result.json())

    return
                

def connect():
    """returns a connection or throws error if cannot connect"""
    res = test_connection(get_credentials())

    if res['code'] != 200:
        frappe.throw("Mailjet credentials might be incorrect")
    else:
        return res['connection']

def insert_mailing_list(doc, method):
    """Sync Email Group on insert in frappe"""

    mailjet = connect()
    
    result = mailjet.contactslist.create(data={
        'Name': doc.name
    })

    """if successful, save the Mailjet ID and last update time to the Email Group"""
    if int(result.status_code) in [200, 201]:
        res = result.json()

        doc = frappe.get_doc("Email Group", doc.name)
        doc.last_update = res['Data'][0]['CreatedAt']
        doc.mailjet_id = res['Data'][0]['ID']
        doc.save( ignore_permissions=True, ignore_version=True )

def update_contact(doc, method):
    from frappe.utils import pretty_date

    creation = pretty_date(doc.creation) #frappe.errprint(pretty_date(doc.updated))
    modified = pretty_date(doc.modified)

    """if record was just created/updated, do not update it after setting the mailjet_id"""
    if creation.lower() == 'just now' or modified.lower() == 'just now': # or modified.lower() == '1 minute ago':
        return
        
    insert_contact(doc, method)

def get_contact_properties(email):
    """Get properties for contact to sync"""
    custom_fields = get_custom_fields()

    # add full_name to custom fields if not already there
    if "first_name" not in custom_fields:
        custom_fields.append("first_name")

    if "first_name" not in custom_fields:
        custom_fields.append("last_name")
        
    settings = frappe.get_cached_doc("Mailjet Settings", "Mailjet Settings")

    # Get the custom fields values from Lead or Request doctype
    key = "email_address"
    if settings.for_doctype == "Lead":
        key = "email_id"
        
    dl = frappe.db.get_list(settings.for_doctype, 
            filters={key: email}, order_by='creation DESC', 
            fields=custom_fields, 
            limit=1 )

    if len(dl) < 1:
        custom_fields.pop(custom_fields.index('event'))
        #custom_fields.pop(custom_fields.index('import_tags'))
        custom_fields.append('event_name')
        if 'company_name' in custom_fields:
            custom_fields.pop(custom_fields.index('company_name'))
            custom_fields.append('company')

        # get Request fields and remove custom fields not in Request
        request_field_docs = frappe.get_meta("Request").fields
        request_fields = [d.fieldname for d in request_field_docs]
        
        for cf in custom_fields:
            if cf not in request_fields:
                custom_fields.pop(custom_fields.index(cf))

        dl = frappe.db.get_list("Request", 
            filters={'email_address': email}, order_by='creation DESC', 
            fields=custom_fields, 
            limit=1 )

        if len(dl) > 0:
            dl[0]['event'] = dl[0]['event_name']
            dl[0].pop('event_name')
            if 'company' in dl[0]:
                dl[0]['company_name'] = dl[0]['company']
                dl[0].pop('company')                

    return dl


def get_custom_fields():
    """Get custom field names from Mailjet Settings"""
    doc = frappe.get_cached_doc("Mailjet Settings", "Mailjet Settings")
    return [d.field_name for d in doc.custom_fields]


def insert_contact(doc, method): # add seg
    """Sync Email Group on insert in frappe"""
    
    mailjet = connect()
    result = {}
    action = "addnoforce"

    contactlist_id = frappe.db.get_value("Email Group", doc.email_group, ['mailjet_id'] )

    if doc.unsubscribed == 1:
        action = "unsub"

    if method == "on_update" and doc.unsubscribed==0:
        action = "addforce"

    properties = get_contact_properties(doc.email)
    if len(properties) < 1:
        # do not sync contacts without properties in either Lead or Request doctype
        p("No properties for d " + doc.email)
        return
    properties = properties[0]
    full_name = str(properties['first_name']) + " " + str(properties['last_name'])

    result = mailjet.contactslist_managecontact.create(id=contactlist_id, data = {
        "IsExcludedFromCampaigns": "false",
        "Name": full_name,
        'Email': doc.email,
        'Action': action,
        "Properties": properties
        
    })
    #print_result(result)
    
    if method != "on_update":
        update_group_member(doc, result)
    return

def update_group_member(doc, result, contacts=None):

    """if successful, save the Mailjet ID and last update time to the Email Group Member"""
    if int(result.status_code) in [200, 201]:
        res = result.json()

        doc = frappe.get_doc("Email Group Member", doc.name)
        doc.last_update = ""
        doc.mailjet_id = res['Data'][0]['ContactID']
        doc.save( ignore_permissions=True, ignore_version=True )

    #print_result(result)
    return
        


def delete_mailing_list(doc, method):
    """Sync deletion of Email Group on confirmation"""

    settings = frappe.get_cached_doc("Mailjet Settings", "Mailjet Settings")

    if settings.delete_sync != "Yes":
        return

    mailjet = connect()
    result = mailjet.contactslist.delete(id=doc.mailjet_id)


@frappe.whitelist(allow_guest=True)
def initialise():
    print("initialise")

    doc = frappe.get_doc("Mailjet Settings")
    verify_credentials(doc)
    setup_custom_fields(doc)
    setup_webhooks(doc)

    print("initialised")

@frappe.whitelist()
def setup_custom_fields(settings=None, method=None):
    """Sync custom fields if not done"""

    if not settings:
        settings = frappe.get_cached_doc("Mailjet Settings", "Mailjet Settings")

    if settings.setup_custom_fields == "No":
        return

    mailjet = connect()
    count = 0
    
    # get caller function name
    import inspect
    caller_function = inspect.stack()[1][3]

    for field in settings.custom_fields:
        if field.synced == 0 or caller_function != "initialise":
            
            result = mailjet.contactmetadata.create(data={
                'Datatype': "str",
                'Name': field.field_name,
                'NameSpace': "static"
            })

            if result.status_code == 201 or (result.status_code == 400 and field.synced == 0):
                field.synced = 1
                count = count + 1
                            
            print_result(result)
    
    if count >= 1:
        frappe.msgprint("Custom fields setup in Mailjet")
        settings.save()
        settings.reload()

def setup_webhooks(doc):
    if doc.setup_webhooks == 1:

        mailjet = connect()
        server_name = frappe.utils.get_url()

        results = []
        error = []
        success = []
        exists = []

        data = {
            'EventType': "open",
            'IsBackup': "false",
            "Version": "2",
            'Status': "alive",
            'Url': server_name + '/mailjet-webhook'
        }
        r = mailjet.eventcallbackurl.create(data=data)

        if r.status_code == 201:
            success.append("open")
        elif r.status_code == 400:
            exists.append("open")
        else:
            error.append("open")

        data = {
            'EventType': "click",
            'IsBackup': "false",
            "Version": "2",
            'Status': "alive",
            'Url': server_name + '/mailjet-webhook'
        }
        r = mailjet.eventcallbackurl.create(data=data)

        if r.status_code == 201:
            success.append("open")
        elif r.status_code == 400:
            exists.append("open")
        else:
            error.append("open")

        data = {
            'EventType': "bounce",
            'IsBackup': "false",
            "Version": "2",
            'Status': "alive",
            'Url': server_name + '/mailjet-webhook'
        }
        r = mailjet.eventcallbackurl.create(data=data)

        if r.status_code == 201:
            success.append("open")
        elif r.status_code == 400:
            exists.append("open")
        else:
            error.append("open")

        data = {
            'EventType': "spam",
            'IsBackup': "false",
            "Version": "2",
            'Status': "alive",
            'Url': server_name + '/mailjet-webhook'
        }
        r = mailjet.eventcallbackurl.create(data=data)

        if r.status_code == 201:
            success.append("open")
        elif r.status_code == 400:
            exists.append("open")
        else:
            error.append("open")

        data = {
            'EventType': "blocked",
            'IsBackup': "false",
            "Version": "2",
            'Status': "alive",
            'Url': server_name + '/mailjet-webhook'
        }
        r = mailjet.eventcallbackurl.create(data=data)

        if r.status_code == 201:
            success.append("open")
        elif r.status_code == 400:
            exists.append("open")
        else:
            error.append("open")

        data = {
            'EventType': "unsub",
            'IsBackup': "false",
            "Version": "2",
            'Status': "alive",
            'Url': server_name + '/mailjet-webhook'
        }
        r = mailjet.eventcallbackurl.create(data=data)

        if r.status_code == 201:
            success.append("open")
        elif r.status_code == 400:
            exists.append("open")
        else:
            error.append("open")

        data = {
            'EventType': "sent",
            'IsBackup': "false",
            "Version": "2",
            'Status': "alive",
            'Url': server_name + '/mailjet-webhook'
        }
        r = mailjet.eventcallbackurl.create(data=data)

        if r.status_code == 201:
            success.append("open")
        elif r.status_code == 400:
            exists.append("open")
        else:
            error.append("open")

        #webhook_message(success, error)


def webhook_message(success, error):

    state = "updated"
    
    if str(sys._getframe(1)) == 'initialised':
        state = "saved"

    frappe.msgprint( _("Successfully {updated} <strong>").format(updated=state) + ', '.join(success) + "</strong> webhooks" )

    if len(error) > 0:
        frappe.msgprint( _("There were errors saving <strong>") + ', '.join(error) + "</strong> webhook(s)" )

        


@frappe.whitelist(allow_guest=True)
def update_webhooks():
    
    doc = frappe.get_doc("Mailjet Settings", "Mailjet Settings")

    if doc.setup_webhooks == 1:
        mailjet = connect()
        result = mailjet.eventcallbackurl.get()
        
        server_name = frappe.utils.get_url()

        hooks = result.json().get('Data')
        
        success = []
        error = []
        for hook in hooks:
            #get_dict_by_value(hooks, 'unsub', email)
            
            result = mailjet.eventcallbackurl.update(id=hook.get('ID'), data={
                'EventType': hook.get('EventType'),
                'IsBackup': "false",
                "Version": "2",
                'Status': "alive",
                'Url': server_name + '/mailjet-webhook'
            })
            if int(result.status_code) in [200, 201]:
                success.append(hook.get('EventType'))
            else:
                error.append(hook.get('EventType'))

        webhook_message(success, error)


def p(*args):
    print(*args)

def ep(msg):
    frappe.errprint(msg)

def remove_contact(doc, method):
    """remove contact from list on delete from frappe"""
    
    mailjet = connect()
    action = "remove"

    contactlist_id = frappe.db.get_value("Email Group", doc.email_group, ['mailjet_id'] )
    result = mailjet.contactslist_managecontact.create(id=contactlist_id, data = {
        'Email': doc.email,
        'Action': action,
        "Properties": {}
    })
    # print_result(result)


def sync_contact_lists(mailjet):
    """send all Email Groups"""

    groups = frappe.db.get_all('Email Group', fields=['name', 'mailjet_id', 'last_update'], limit=0)

    list = mailjet.contactslist.get(filters = {
        'limit': 0
    })

    if list.status_code in [200, 201]:

        names = []
        list = list.json()['Data']
        for l in list:
            names.append(l['Name'])

        #print("{:80}|{:^30}|{:^30}|".format("name", "frappe_id", "mj_id"))
        for group in groups:

            if group.name not in names:
                data = {
                    'Name': group.name
                }
                result = mailjet.contactslist.create(data=data)

                """if successful, save the Mailjet ID and last update time to the Email Group"""
                if int(result.status_code) == 201:
                    res = result.json()

                    doc = frappe.get_doc("Email Group", group.name)
                    doc.last_update = res['Data'][0]['CreatedAt']
                    doc.mailjet_id = res['Data'][0]['ID']
                    doc.save( ignore_permissions=True, ignore_version=True ) 

            # generate an else statement if group.name is found in names and doc.maijet_id is different from res['Data'][0]['ID'], update it in the doc
            else:               
                mj_list = get_dict_by_value(list, 'Name', group.name)
            
                if group.mailjet_id != mj_list.get('ID', ''):
                    doc = frappe.get_doc("Email Group", group.name)
                    doc.last_update = mj_list.get('CreatedAt', '')
                    doc.mailjet_id = mj_list.get('ID', '')
                    doc.save( ignore_permissions=True, ignore_version=True )
        
            # get ID from list using group.name
            #mj_list = get_dict_by_value(list, 'Name', group.name)
            #print("{:80}|{:^30}|{:^30}|".format(str(group.name), str(group.mailjet_id), mj_list.get('ID', '')))

    return


def sync_campaigns(mailjet=None):
    """ called by by cronjob in hooks.py """

    if not mailjet:
        mailjet = connect()
    
    result = mailjet.campaign.get(filters={
        'Limit': 0,
        'Period': 'Year'
    })

    if int(result.status_code) in [200, 201]:
        campaigns = result.json()['Data']

        for campaign in campaigns:

            result = mailjet.statcounters.get(filters = {
                'SourceId': campaign.get('ID'),
                'CounterSource': 'Campaign',
                'CounterTiming': 'Message',
                'CounterResolution': 'Lifetime'
            })
            
            #print_result(result)

            stats = result.json()['Data'][0]

            sent = stats.get('MessageSentCount')
            opens = stats.get('MessageOpenedCount')
            clicks = stats.get('MessageClickedCount')
            blocked = stats.get('MessageBlockedCount')
            unsubs = stats.get('MessageUnsubscribedCount')
            spam_reports = stats.get('MessageSpamCount')
            hard_bounces = stats.get('MessageHardBouncedCount')
            soft_bounces = stats.get('MessageSoftBouncedCount')
            sender = campaign.get('FromEmail')
            delivered = sent - (hard_bounces + soft_bounces)

            # delivered shouldnt be negative
            if delivered < 0:
                delivered = 0
            
            try:
                doc = frappe.get_doc('Mailjet Email Campaign', campaign.get('ID'))

                doc.sent = sent
                doc.opens = opens
                doc.clicks = clicks
                doc.blocked = blocked
                doc.unsubs = unsubs
                doc.sender = sender
                doc.spam_reports = spam_reports
                doc.hard_bounces = hard_bounces
                doc.soft_bounces = soft_bounces
                doc.delivered = delivered           

                doc.save(ignore_permissions=True, ignore_version=True)     

            except frappe.exceptions.DoesNotExistError:
                event_name = "No Related Event"
                contact_list = "No Related Contact List"

                if frappe.db.exists('Email Group', {'mailjet_id': campaign.get('ListID')}):
                    event = frappe.get_list('Email Group', fields=['name', 'event'], limit=1, filters={
                        'mailjet_id': campaign.get('ListID')
                    })
                    
                    event_name = event[0].event
                    contact_list = event[0].name

                # create it
                doc = frappe.get_doc({
                    'doctype': 'Mailjet Email Campaign',
                    'title': campaign.get('Subject'),
                    'mailjet_id': campaign.get('ID'),
                    'contact_list': contact_list,
                    'sender': campaign.get('FromEmail'),
                    'event_name': event_name,
                    'sent': sent,
                    'opens': opens,
                    'clicks': clicks,
                    'blocked': blocked,
                    'unsubs': unsubs,
                    'spam_reports': spam_reports,
                    'hard_bounces': hard_bounces,
                    'soft_bounces': soft_bounces,
                    'delivered': delivered
                })
                doc.insert(ignore_permissions=True)
            except Exception as e:
                print(e)
    return


frappe.whitelist(allow_guest=True)
def mailjet_webhook(args):
    """syncs all mailjet events as """
    mailjet = connect()

    for a in args:
        #frappe.errprint(frappe.request.data)
        data = frappe._dict(a)

        p(a)

        campaign = ""

        if data.mj_campaign_id: 
            campaign = data.mj_campaign_id 
            if not frappe.db.exists('Mailjet Email Campaign', data.mj_campaign_id):
                sync_campaigns(mailjet=None)

        match data.event:
            case 'sent':

                # create log entry
                doc = frappe.get_doc({
                    'doctype': 'Mailjet Webhook Log',
                    'event_type': data.event,
                    'email': data.email,
                    'campaign': campaign,
                    'mailjet_id': data.mj_contact_id
                })
                
                doc.insert(ignore_permissions=True)
                doc.submit()

            case 'open':
                # create log entry
                doc = frappe.get_doc({
                    'doctype': 'Mailjet Webhook Log',
                    'event_type': data.event,
                    'email': data.email,
                    'campaign': campaign,
                    'mailjet_id': data.mj_contact_id,
                    'country': data.geo
                })
                
                doc.insert(ignore_permissions=True)
                doc.submit()

            case 'click':
                # create log entry
                doc = frappe.get_doc({
                    'doctype': 'Mailjet Webhook Log',
                    'event_type': data.event,
                    'email': data.email,
                    'campaign': campaign,
                    'mailjet_id': data.mj_contact_id,
                    'country': data.geo,
                    'url': data.url
                })
                
                doc.insert(ignore_permissions=True)
                doc.submit()

            case 'spam':
                # create log entry
                doc = frappe.get_doc({
                    'doctype': 'Mailjet Webhook Log',
                    'event_type': data.event,
                    'email': data.email,
                    'campaign': campaign,
                    'mailjet_id': data.mj_contact_id,
                    'country': data.geo,
                    'source': data.source
                })
                
                doc.insert(ignore_permissions=True)
                doc.submit()

            case 'unsub':
                # create log entry
                doc = frappe.get_doc({
                    'doctype': 'Mailjet Webhook Log',
                    'event_type': data.event,
                    'email': data.email,
                    'campaign': campaign,
                    'mailjet_id': data.mj_contact_id,
                    'country': data.geo
                })
                
                doc.insert(ignore_permissions=True)
                doc.submit()

                # update the correct email group
                if frappe.db.exists({'doctype': 'Email Group Member', 'email': data.email }):
                    mail_group = frappe.db.get_list("Email Group", filters={"mailjet_id": data.mj_list_id}, limit=1)
                    if mail_group:
                        member = frappe.db.get_list("Email Group Member", filters={"email": data.email, "email_group": mail_group[0].name}, fields=["name"], limit=1)[0]
                        frappe.db.set_value("Email Group Member", member.name, "unsubscribed", 1)

            case 'blocked':
                doc = frappe.get_doc({
                    'doctype': 'Mailjet Webhook Log',
                    'event_type': data.event,
                    'email': data.email,
                    'campaign': campaign,
                    'mailjet_id': data.mj_contact_id,
                    'payload': data.Payload,
                    'error_title': data.error_related_to,
                    'error': data.error
                })
                
                doc.insert(ignore_permissions=True)
                doc.submit()

            case 'bounce':
                doc = frappe.get_doc({
                    'doctype': 'Mailjet Webhook Log',
                    'event_type': data.event,
                    'email': data.email,
                    'campaign': campaign,
                    'mailjet_id': data.mj_contact_id,
                    'payload': data.Payload,
                    'country': data.geo,
                    'blocked': data.blocked,
                    'hard_bounce': data.hard_bounce,
                    'error_title': data.error,
                    'error': data.comment
                })
                
                doc.insert(ignore_permissions=True)
                doc.submit()

            case _:
                frappe.errprint('failed to save webhook event')
                frappe.errprint(data)
                