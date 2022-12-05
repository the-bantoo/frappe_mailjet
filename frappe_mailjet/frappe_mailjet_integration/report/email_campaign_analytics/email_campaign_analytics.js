// Copyright (c) 2022, Bantoo and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Email Campaign Analytics"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "event_name",
			"label": __("Event"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Events"
		},
		{
			"fieldname": "campaign",
			"label": __("Campaign"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Mailjet Email Campaign",
		},
		{
			"fieldname": "contact_list",
			"label": __("Contact List"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Email Group"
		}
	]
};