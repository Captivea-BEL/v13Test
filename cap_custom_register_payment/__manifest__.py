# -*- coding: utf-8 -*-

{
    "name": "CAP Register Payment", 
    "version": "13.0.0.1.1",
    "author": "", 
    "category": "Account", 
    "description": """
        Custom Register Payment for discount payment terms.
    """,
    'author': "Captivea",
    'website': "www.captivea.us",
    "depends": [
        "account"
    ], 
    "data": [
        'views/account_move_view.xml',
        'views/res_config_settings_view.xml',
        'views/res_partner_view.xml',
        'wizard/account_payment_register_view.xml'
    ],
}
