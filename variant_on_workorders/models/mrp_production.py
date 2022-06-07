from odoo import models, api, fields


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    custom_val = fields.Char(string='Custom Value')

    def _prepare_workorder_vals(self, operation, workorders, quantity):
        # Inherited to add custom_value
        self.ensure_one()
        values = super(MrpProduction, self)._prepare_workorder_vals(operation, workorders, quantity)
        values.update({'custom_val': self.custom_val,})
        return values
