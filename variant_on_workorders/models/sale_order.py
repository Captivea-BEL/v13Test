from odoo import models, api, fields


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    custom_val = fields.Char(string='Custom Value')

    def _prepare_procurement_values(self, group_id=False):
        # Inherited to add custom_value
        values = super(SaleOrderLine, self)._prepare_procurement_values(group_id)
        values.update({'custom_val': self.custom_val,})
        return values


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def write(self, vals):
        # Inherited to get the attribute values 
        res = super(SaleOrder, self).write(vals)
        for line in self.order_line:
            desc_list = line.name.split('\n')
            if desc_list and len(desc_list) >= 3:
                line.custom_val = False
                for desc in desc_list[2:]:
                    attrib_value = desc.split(':')[1] + ':' + desc.split(':')[2]
                    value = attrib_value.strip()
                    if line.custom_val:
                        value = line.custom_val + ', ' + attrib_value.strip()
                    line.custom_val = value
        return res
