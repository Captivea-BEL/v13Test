# -*- coding: utf-8 -*-
{
    'name': "Product Variant on WorkOrders",
    'summary': """
        This module displays the custom value of variant on
        manufacturing order and workorder when created from sale order
        """,
    'description': """
        This module displays the custom value of variant on
        manufacturing order and workorder when created from sale order
        """,
    'author': "Captivea",
    'website': "www.captivea.us",
    'category': 'Sales/Sales',
    'version': '13.0.1.0.5',
    'depends': ['product', 'sale_management', 'mrp_workorder', 'mrp'],
    'data': [
        'views/sale_order_views.xml',
        'views/stock_move_views.xml',
        'views/mrp_production_view.xml',
        'views/mrp_workorder_views.xml',
        'views/mrp_bom_views.xml',
    ],
}
