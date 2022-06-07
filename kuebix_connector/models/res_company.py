# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    # Inherited to add Kuebix credential fields
    _inherit = 'res.company'

    username = fields.Char(string='Username')
    password = fields.Char(string='Password')
    client_id = fields.Char(string='Client ID')
