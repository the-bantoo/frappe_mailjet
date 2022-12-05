# Copyright (c) 2022, Bantoo and contributors
# For license information, please see license.txt


import frappe
from frappe import _

from typing import Any, Dict, List, Optional, TypedDict
from frappe.query_builder.functions import CombineDatetime
from frappe.utils import cint, date_diff, flt, getdate


class StockBalanceFilter(TypedDict):
    from_date: str
    to_date: str
    event: Optional[str]
    email_list: Optional[str]
    campaign: Optional[str]
    

def execute(filters=None):
    return get_columns(), get_data(filters)

def make_where_filters(filters):
    start = filters.from_date
    end = filters.to_date
    event = filters.event
    email_list = filters.email_list
    campaign = filters.campaign
    where = ""
    dates = "where cast(`creation` as date) between {start} and {end}".format(start=frappe.db.escape(start), end=frappe.db.escape(end))

    if event:
        groups = frappe.get_list("Email Group", fields=['name'], filters={'event': event})
        where = " and `mailjet_list_id` in ({groups})".format(groups = ', '.join([frappe.db.escape(g.name, percent=False) for g in groups]))

    if email_list:
        where = where + " and `mailjet_list_id` = {email_list}".format(email_list=frappe.db.escape(email_list))

    if campaign:
        where = where + " and `campaign` = {campaign}".format(campaign=frappe.db.escape(campaign))

    return dates + where

def p(v):
    frappe.errprint(v)

def get_data(filters):
    data = []

    sql = """
            select `creation`, `event_type`, `email`, min(`campaign`) as campaign, count(event_type) as event_count, 
                    GROUP_CONCAT(DISTINCT event_type) as actions, GROUP_CONCAT(DISTINCT url) as url, count(hard_bounce) as hard_bounce, `error`,
                    SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END) AS clicks
                from `tabMailjet Webhook Log` 
                
                {where} 
                and docstatus = 1

            group by `campaign`, `email`
            order by `campaign`, `email`, `tabMailjet Webhook Log`.docstatus asc, `tabMailjet Webhook Log`.`modified` DESC;""".format(where=make_where_filters(filters))

    logs = frappe.db.sql(sql, as_dict=1)
    
    # issue
    # unsub wont change on resub - sort by date and pick the last

    for l in logs:
        frappe.errprint(l)
        sender = "ERPNext"
        event_name = "Transactional"
        title = "Transactional"


        if l.campaign:
            campaign = frappe.get_cached_doc('Mailjet Email Campaign', l.campaign)
            sender = campaign.sender
            event_name = campaign.event_name
            title = campaign.title

        opened = 'No'

        if('bounce' in l.actions):
            opened = 'No'
        if('open' in l.actions) or ('click' in l.actions) or ('soft_bounce' in l.actions):
            opened = 'Yes'
        
        # conditions can be improved
        status = "Delivered"
        if('bounce' in l.actions):
            status = 'Bounced'
        elif('unsub' in l.actions):
            status = 'Unsubscribed'
        elif('click' in l.actions):
            status = 'Clicked'
        elif('open' in l.actions):
            status = 'Opened'
        else:
            status = 'Sent'
        
        data.append([l.email, sender, event_name, title, opened, l.url, status, l.clicks])
    
    return data

def get_columns():
    return [
        {
            "label": _("Recipient"),
            "fieldname": "email",
            "fieldtype": "Data",
            "width": 175,
        },
        {
            "label": _("Sender"),
            "fieldname": "sender",
            "fieldtype": "Data",
            "width": 175,
        },
        {
            "label": _("Event"),
            "fieldname": "campaign.event_name",
            "fieldtype": "Data",
            "width": 199,
        },
        {
            "label": _("Newsletter"),
            "fieldname": "campaign.title",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Opened"),
            "fieldname": "opened",
            "fieldtype": "Data",
            "width": 75,
        },
        {
            "label": _("Link"),
            "fieldname": "url",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": _("Clicks"),
            "fieldname": "actions",
            "fieldtype": "Int",
            "width": 70,
        },
    ]

