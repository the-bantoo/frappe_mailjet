import frappe
from frappe import _, exceptions
import subprocess
import sys
import time


def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    frappe.errprint(package + " has been installed")

try:
    import mailjet_rest
except:
    # ModuleNotFoundError
    install("mailjet_rest")

from mailjet_rest import Client


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
def sync(): # issue 1
    print('mailjet sync start')

    connection = connect()

    sync_mailing_lists(connection)
    sync_campaigns(connection)
    sync_contacts(connection)

    print('maijet sync complete')



def sync_contacts(mailjet):
    """Sync all Email Group Members to mailjet as contacts"""

    list = mailjet.contactslist.get(filters = {
        'limit': 0
    })

    if list.status_code == 200:
        contact_list = list.json()['Data']

        for cl in contact_list:
            contact_list = cl['Name']
            contacts = frappe.db.get_all('Email Group Member', fields={'name', 'email', 'mailjet_id', 'unsubscribed'}, limit=0, filters={
                'email_group': contact_list
            })

            if len(contacts) > 0:
                sub_data = []
                unsub_data = []
                for contact in contacts:  
                    """
                    country
                    firstname
                    name
                    newsletter_sub
                    """ 

                    request_doc = frappe.db.get_list("Request", filters={'email_address': contact.email}, order_by='creation DESC', 
                        fields=['full_name', 'country', 'first_name', 'last_name', 'event_name', 'company', 'job_title'], 
                        limit=1 )

                    full_name  = ""
                    country = ""
                    first_name = ""
                    last_name = ""
                    event_name = ""
                    company = ""
                    job_title = ""
                    
                    if request_doc:
                        full_name = request_doc[0].full_name
                        country = request_doc[0].country
                        first_name = request_doc[0].first_name
                        last_name = request_doc[0].last_name
                        event_name = request_doc[0].event_name
                        company = request_doc[0].company
                        job_title = request_doc[0].job_title
                    
                    """create list of subscribed and unsubs and post separately"""
                    if contact.unsubscribed == 0:

                        sub_data.append({
                            'Email': contact.email,
                            "Name": full_name,
                            "IsExcludedFromCampaigns": "false",
                            "Properties": {
                                'name': full_name,
                                'firstname': first_name,
                                'country': country,
                                'lastname': last_name,
                                'eventname': event_name,
                                'company': company,
                                'jobtitle': job_title
                            }
                        })
                    else:

                        unsub_data.append({
                            'Email': contact.email,
                            "Name": full_name,
                            "IsExcludedFromCampaigns": "true",
                            "Properties": {
                                'name': full_name,
                                'firstname': first_name,
                                'country': country,
                                'lastname': last_name,
                                'eventname': event_name,
                                'company': company,
                                'jobtitle': job_title
                            }
                        })

                
                contactlist_id = frappe.db.get_value("Email Group", contact_list, ['mailjet_id'] )

                if sub_data:
                    result = mailjet.contactslist_managemanycontacts.create(id=contactlist_id , data={
                        'Action': "addnoforce",
                        'Contacts': sub_data
                    })
                
                if unsub_data:
                    result = mailjet.contactslist_managemanycontacts.create(id=contactlist_id , data={
                        'Action': "unsub",
                        'Contacts': unsub_data
                    })

                update_contacts_by_list(contact_list, contactlist_id, contacts, mailjet)

                # print_result(result)

                    
def update_contacts_by_list(contact_list, contactlist_id=None, members=None, mailjet=None):
    """Get IDs and updated time"""

    if not mailjet:
        mailjet = connect()
    
    if not members:
        members = frappe.db.get_all('Email Group Member', fields={'name', 'email', 'mailjet_id', 'unsubscribed'}, limit=0, filters={
                'email_group': contact_list
            })
        
    result = mailjet.contact.get(filters = {
        'Limit': 0,
        'ContactsList': contactlist_id,
    })
    #print_result(result)

    if result.status_code == 200:

        #frappe.errprint(result.json()['Data'])

        member_emails = []
        for m in members:
            member_emails.append(m.email)
            
        for contact in result.json()['Data']:
            email = contact['Email']
            
            if email in member_emails:
                member = get_dict_by_value(members, 'email', email)

                if str(contact['ID']) != str(member.get('mailjet_id')):
                    """only update records if they have a de-similar IDs"""

                    doc = frappe.get_doc( "Email Group Member", member.get('name') )
                    
                    doc.last_update = contact['LastUpdateAt']
                    doc.mailjet_id = contact['ID']
                    doc.save( ignore_permissions=True, ignore_version=True )
                
                """only update subscription status if the two systems are different"""
                
                frappe_subbed_mailjet_unsubbed = ( (contact['UnsubscribedBy'] != "") and (member.get('unsubcribed') == 0) )

                if frappe_subbed_mailjet_unsubbed:
                    doc = frappe.get_doc( "Email Group Member", member.get('name') )
                    
                    doc.last_update = contact['LastUpdateAt']
                    doc.unsubcribed = 1
                    doc.save( ignore_permissions=True, ignore_version=True )


def get_dict_by_value(dict_list, field, value):
    """returns dictionary with specific value in given field"""
    for d in dict_list:
        if d.get(field) == value:
            return d

def print_result(result):

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
    if result.status_code == 201:
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
    if creation == 'just now' or modified == 'just now':
        return
    
    insert_contact(doc, method)


def insert_contact(doc, method):
    """Sync Email Group on insert in frappe"""
    
    mailjet = connect()
    result = {}
    action = "addnoforce"

    contactlist_id = frappe.db.get_value("Email Group", doc.email_group, ['mailjet_id'] )
    
    request_doc = frappe.db.get_list("Request", 
        filters={'email_address': doc.email}, order_by='creation DESC', 
        fields=['full_name', 'country', 'first_name', 'last_name', 'event_name', 'company', 'job_title'], 
        limit=1 )
    
    full_name  = ""
    country = ""
    first_name = ""
    last_name = ""
    event_name = ""
    company = ""
    job_title = ""
    
    if request_doc:
        full_name = request_doc[0].full_name
        country = request_doc[0].country
        first_name = request_doc[0].first_name
        last_name = request_doc[0].last_name
        event_name = request_doc[0].event_name
        company = request_doc[0].company
        job_title = request_doc[0].job_title
    
    if doc.unsubscribed == 1:
        action = "unsub"

    if method == "on_update" and doc.unsubscribed==0:
        action = "addforce"

    result = mailjet.contactslist_managecontact.create(id=contactlist_id, data = {
        "IsExcludedFromCampaigns": "false",
        'Email': doc.email,
        "Name": full_name,
        'Action': action,
        "Properties": {
            'name': full_name,
            'firstname': first_name,
            'country': country,
            'lastname': last_name,
            'eventname': event_name,
            'company': company,
            'jobtitle': job_title
        }
    })
        
    # print_result(result)

    if method != "on_update":
        update_group_member(doc, result)
    return

def update_group_member(doc, result, contacts=None):

    """if successful, save the Mailjet ID and last update time to the Email Group Member"""
    if result.status_code == 201:
        res = result.json()

        doc = frappe.get_doc("Email Group Member", doc.name)
        doc.last_update = ""
        doc.mailjet_id = res['Data'][0]['ContactID']
        doc.save( ignore_permissions=True, ignore_version=True )

    #print_result(result)
    return
        


def delete_mailing_list(doc, method):
    """Sync deletion of Email Group on confirmation"""

    settings = frappe.get_doc("Mailjet Settings")

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

def setup_custom_fields(doc):
    """Sync custom fields if not done"""

    if doc.setup_custom_fields == "No":
        return

    mailjet = connect()
    count = 0

    for field in doc.custom_fields:
        if field.synced == 0:
            
            result = mailjet.contactmetadata.create(data={
                'Datatype': "str",
                'Name': field.field_name,
                'NameSpace': "static"
            })

            if result.status_code == 201:
                field.synced = 1
                count = count + 1
    
    if count >= 1:
        frappe.msgprint("Custom fields setup in Mailjet")
        doc.save()

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
            if result.status_code == 200:
                success.append(hook.get('EventType'))
            else:
                error.append(hook.get('EventType'))

        webhook_message(success, error)


def p(*args):
    print(*args)

def remove_contact(doc, method):
    """remove contact from list on delete from frappe"""
    
    mailjet = connect()
    action = "remove"

    contactlist_id = frappe.db.get_value("Email Group", doc.email_group, ['mailjet_id'] )
        
    request_doc = frappe.db.get_list("Request", 
        filters={'email_address': doc.email}, order_by='creation DESC', 
        fields=['full_name', 'country', 'first_name', 'last_name', 'event_name', 'company', 'job_title'], 
        limit=1 )

    full_name  = ""
    country = ""
    first_name = ""
    last_name = ""
    event_name = ""
    company = ""
    job_title = ""
    
    if request_doc:
        full_name = request_doc[0].full_name
        country = request_doc[0].country
        first_name = request_doc[0].first_name
        last_name = request_doc[0].last_name
        event_name = request_doc[0].event_name
        company = request_doc[0].company
        job_title = request_doc[0].job_title

    result = mailjet.contactslist_managecontact.create(id=contactlist_id, data = {
        'Email': doc.email,
        "Name": full_name,
        'Action': action,
        "Properties": {
            'name': full_name,
            'firstname': first_name,
            'country': country,
            'lastname': last_name,
            'eventname': event_name,
            'company': company,
            'jobtitle': job_title
        }
    })
    # print_result(result)


def sync_mailing_lists(mailjet):
    """send all Email Groups"""

    groups = frappe.db.get_all('Email Group')

    list = mailjet.contactslist.get(filters = {
        'limit': 0
    })

    if list.status_code == 200:

        names = []
        list = list.json()['Data']
        for l in list:
            names.append(l['Name'])

        for group in groups:
            if group.name not in names:
                data = {
                    'Name': group.name
                }
                result = mailjet.contactslist.create(data=data)

                """if successful, save the Mailjet ID and last update time to the Email Group"""
                if result.status_code == 201:
                    res = result.json()

                    doc = frappe.get_doc("Email Group", group.name)
                    doc.last_update = res['Data'][0]['CreatedAt']
                    doc.mailjet_id = res['Data'][0]['ID']
                    doc.save( ignore_permissions=True, ignore_version=True )
    return


def sync_campaigns(mailjet=None):
    """ called by by cronjob in hooks.py """

    if not mailjet:
        mailjet = connect()
    
    result = mailjet.campaign.get(filters={
        'Limit': 0,
        'Period': 'Year'
    })

    if result.status_code == 200:
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
                doc.submit(), 

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
                doc.submit(), 

            case _:
                frappe.errprint(data)