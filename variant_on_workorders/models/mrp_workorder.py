from odoo import models, api, fields


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    custom_val = fields.Char(string='Custom Value')