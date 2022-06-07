from odoo import models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    def _get_action(self, action_xmlid):
        res = super(StockPickingType, self)._get_action(action_xmlid=action_xmlid)
        if res:
            context = res.get('context', {})
            context.update({'picking_type_code': self.code})
            res.update({'context': context})
        return res