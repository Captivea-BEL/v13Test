from odoo import models, fields


class FetchCarrierRates(models.Model):
    _name = 'fetch.carrier.rates'
    _description = 'Fetch Carrier Rates'

    name = fields.Char(string='Name')
    code = fields.Char(string='Scac')
    service_type = fields.Char(string='Service Type')
    service = fields.Char(string='Service')
    total_price = fields.Float(string='Total Price')
    sale_id = fields.Many2one('sale.order', string='Sale Order')
    # accessorial_name = fields.Char(string='Accessorial Name')
    # accessorial_type = fields.Char(string='Accessorial Type')
    # accessorial_price = fields.Float(string='Accessorial Price')
    
    # def name_get(self):
    #     if self._context.get('carrier_name_with_rate'):
    #         res = []
    #         for carrier in self:
    #             name = '%s - %s'% (carrier.name, carrier.total_price)
    #             res.append((carrier.id, name))
    #         return res
    #     return super(FetchCarrierRates, self).name_get()
    
    def name_get(self):
        if self._context.get('carrier_name_with_rate'):
            return [(carrier.id, '%s - %s - %s' % (carrier.name, carrier.service, carrier.total_price)) for carrier in self]
        else:
            return [(carrier.id, '%s - %s - %s' % (carrier.name, carrier.service, carrier.total_price)) for carrier in self]
    
    def add_shipping_price(self):
        rec = self.env['delivery.carrier'].search(
            [('delivery_type', '=', 'kuebix')], limit=1)
        if not rec:
            product_id = self.env['product.product'].create({
                'name': 'Kuebix delivery',
                'type': 'service',
                'taxes_id': False,
                'list_price': 0.0
            })
            rec = self.env['delivery.carrier'].create({
                'name': 'Kuebix',
                'delivery_type': 'kuebix',
                'product_id': product_id.id,
            })
        self.sale_id.scac = self.code
        self.sale_id.service_name = self.service
        self.sale_id.set_delivery_line(rec, self.total_price)
        action = self.env.ref(
            'sale.action_quotations_with_onboarding').read()[0]
        action['res_id'] = self.sale_id.id
        action['views'] = [[self.env.ref('sale.view_order_form').id, 'form']]
        return action

    def delete_carrier_rates(self):
        # Method to delete carrier rates
        self.search([('sale_id', '=', self.sale_id.id)]).unlink()
        action = self.env.ref(
            'kuebix_connector.view_fetch_carrier_rates_action').read()[0]
        action['res_id'] = self.id
        action['views'] = [[self.env.ref(
            'kuebix_connector.fetch_carrier_rates_tree_view').id, 'tree']]
        return action
