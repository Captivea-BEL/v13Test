# -*- coding: utf-8 -*-
{
    "name": "Kuebix Connector",
    "version": "10",
    "author": "Captivea",
    "category": "Operations/Inventory/Delivery",
    "description": """
        Module to fetch shipping cost from Kuebix.
    """,
    'website': "www.captivea.us",
    "depends": [
        "delivery","base", "sale", "stock",
    ],
    "data": [
        'security/ir.model.access.csv',
        'views/fetch_carrier_rates_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml'
    ],
    "installable": True,
    "auto_install": False,
}
