from odoo import models, api, fields


class StockMove(models.Model):
    _inherit = "stock.move"

    custom_val = fields.Char(string='Custom Value')

    def _prepare_procurement_values(self):
    	# Inherited to add custom_value
        self.ensure_one()
        values = super(StockMove, self)._prepare_procurement_values()
        values.update({'custom_val': self.custom_val,})
        return values