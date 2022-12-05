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
    event_name: Optional[str]
    contact_list: Optional[str]
    campaign: Optional[str]
    

def execute(filters=None):
    return get_columns(), get_data(filters)

def make_where_filters(filters):
    from frappe.utils.data import add_to_date
    
    start = filters.from_date
    end = filters.to_date #add_to_date(filters.to_date, days=1)
    event_name = filters.event_name
    contact_list = filters.contact_list
    campaign = filters.campaign
    where_str = ""
    dates = """where cast(`creation` as date) between '{start}' and '{end}'""".format(start=start, end=end)

    if event_name:
        where_str = """ and `event_name` = '{event_name}'""".format(event_name=event_name)

    if contact_list:
        where_str = where_str + """ and `contact_list` = '{contact_list}'""".format(contact_list=contact_list)

    if campaign:
        where_str = where_str + """ and `name` = '{campaign}'""".format(campaign=campaign)

    where = dates + where_str 
    return where


def get_data(filters):
    data = []

    sql = """select *
                from `tabMailjet Email Campaign` 
                
                {where}

                order by `modified` DESC
    """.format(where=make_where_filters(filters))

    logs = frappe.db.sql(sql, as_dict=1)
    print(sql)

    for l in logs:
        data.append({
                'title': str(l.title),
                'event_name': l.event_name,
                'contact_list': l.contact_list,
                'sent': int(l.sent or 0),
                'delivered': int(l.delivered or 0),
                'opens': int(l.opens or 0),
                'clicks': int(l.clicks or 0),
                'spam_reports': int(l.spam or 0),
                'unsubs': int(l.unsubs or 0),
                'blocked': int(l.blocked or 0),
                'soft_bounces': int(l.soft_bounces or 0),
                'hard_bounces': int(l.hard_bounces or 0),
                'sender': l.sender
            })
    
    return data

def get_columns():
    return [
        {
            "label": _("Campaign"),
            "fieldname": "title",
            "fieldtype": "Link",
            "options": "Mailjet Email Campaign",
            "width": 175,
        },
        {
            "label": _("Contact List"),
            "fieldname": "contact_list",
            "fieldtype": "Link",
            "options": "Email Group",
            "width": 200,
        },
        {
            "label": _("Sent"),
            "fieldname": "sent",
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "label": _("Delivered"),
            "fieldname": "delivered",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Opens"),
            "fieldname": "opens",
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "label": _("Clicks"),
            "fieldname": "clicks",
            "fieldtype": "Int",
            "width": 75,
        },
        {
            "label": _("Spam Reports"),
            "fieldname": "spam_reports",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Unsubscribed"),
            "fieldname": "unsubs",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Blocked"),
            "fieldname": "blocked",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Soft Bounces"),
            "fieldname": "soft_bounces",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Hard Bounces"),
            "fieldname": "hard_bounces",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Sender"),
            "fieldname": "sender",
            "fieldtype": "Data",
            "width": 175,
        },
    ]

