

from odoo import models, fields


class ResPartner(models.Model):
    
    _inherit = 'res.partner'
    
    liftgate_required = fields.Selection([('yes','Yes'),('no','No')], default=False, string="Liftgate Required?")
    residential = fields.Boolean(default=False, string="Residential Address?")
    appointment_required = fields.Selection([('yes','Yes'),('no','No')], default=False, string="Appointment Required?")
