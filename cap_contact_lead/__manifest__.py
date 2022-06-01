# -*- coding: utf-8 -*-
{
    'name': "Contact/Lead Information",
    'summary': """
        Display Contact and Lead information in single view
        """,
    'description': """
        Display Contact and Lead information in single view
        """,
    'author': "Captivea",
    'website': "www.captivea.us",
    'category': 'Sales/CRM',
    'version': '1.5',
    'depends': ['crm', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/contact_lead_views.xml',
    ],
}
