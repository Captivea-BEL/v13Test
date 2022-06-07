

from odoo import fields, models, api, _
from odoo.exceptions import MissingError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    def _get_default_carriers(self):
        for rec in self:
            carrier_ids = self.env["fetch.carrier.rates"].search([("sale_id","=",rec.id)])
            rec.kuebix_carrier_ids = [(6,0,carrier_ids.ids)]
    
    carrier_count = fields.Integer(
        string='Carrier Rates', compute='_get_carrier_count')
    paymenttype = fields.Selection([
        ('inbound_collect', 'Inbound Collect'),
        ('outbound_collect', 'Outbound Collect'),
        ('outbound_prepaid', 'Outbound Prepaid'),
        ('third_party', 'Third Party'),
        ('third_party_collect', 'Third Party Collect'),
        ('vendor_delivered', 'Vendor Delivered')],
        string='Payment Type', default='outbound_prepaid')
    scac = fields.Char(string="scac")
    service_name = fields.Char(string="Service")
    liftgate_required = fields.Selection(related='partner_shipping_id.liftgate_required', string="Liftgate Required?", required=True, readonly=False)
    residential = fields.Boolean(related='partner_shipping_id.residential', string="Residential", readonly=False)
    shipping_service_quote = fields.Char(string="Shipping Service Selected", compute='_get_shipping_service_quote') # compute
    shipment_type = fields.Selection([('parcel','Parcel'),('ltl','LTL'),('tl','TL')], string="Type of Shipment", default='parcel', help = 'True if the order is shipped via Parcel', readonly=True)
    shipment_mode = fields.Selection([('air','Air'),('bulk','Bulk'),('dry_van','Dry Van'),('flatbed','Flatbed'),('intermodal','Intermodal'),('ocean','Ocean'),('otr','OTR'),('temp_controlled','Temp Controlled')], string="Shipment Mode",default='dry_van', readonly=True)
    kuebix_carrier_ids = fields.Many2many("fetch.carrier.rates", compute='_get_default_carriers')
    kuebix_carrier_id = fields.Many2one("fetch.carrier.rates", string="Carrier")
    appointment_required = fields.Selection(related="partner_shipping_id.appointment_required", string="Appointment Required?", readonly=False)


    def _get_shipping_service_quote(self):
        for rec in self:
            rec.shipping_service_quote = rec.name + ' - ' + (dict(rec._fields['shipment_type'].selection).get(rec.shipment_type) or '')

    def set_ship_prod_sol(self):
        for rec in self:
            if not rec.kuebix_carrier_id:
                raise ValidationError(_("Please select a specific carrier."))
            elif rec.kuebix_carrier_id:
                del_rec = self.env['delivery.carrier'].search(
                [('delivery_type', '=', 'kuebix')], limit=1)
                if not del_rec:
                    product_id = self.env['product.product'].create({
                        'name': 'Kuebix delivery',
                        'type': 'service',
                        'taxes_id': False,
                        'list_price': 0.0
                    })
                    del_rec = self.env['delivery.carrier'].create({
                        'name': 'Kuebix',
                        'delivery_type': 'kuebix',
                        'product_id': product_id.id,
                    })
                rec.scac = rec.kuebix_carrier_id.code
                rec.service_name = rec.kuebix_carrier_id.service
                total_price = rec.kuebix_carrier_id.total_price + ((rec.kuebix_carrier_id.total_price * del_rec.margin) / 100.0)
                rec.set_delivery_line(del_rec, total_price)
    
    def fetch_all_carrier(self):
        if self.state != 'draft':
            raise ValidationError(_("Reset the sale order to draft state to fetch carrier rates!"))
        existing_sale_carrier_ids = self.env["fetch.carrier.rates"].search([('sale_id', '=', self.id)])
        if existing_sale_carrier_ids:
            for carrier in existing_sale_carrier_ids:
                carrier.unlink()
        record = self.env['delivery.carrier'].get_kuebix_rates(self)
        if record and record.get('rateMap'):
            rateMap = record.get('rateMap')
            for carrier in rateMap.keys():
                for data in rateMap[carrier]:
                    if not data.get('errorMessage'):
                        if data.get('accessorialCharges') and \
                                data.get('accessorialPrice') > 0:
                            for accessorialcharges in \
                                    data.get('accessorialCharges'):
                                if accessorialcharges.get('charge') > 0:
                                    accessorial = accessorialcharges.get(
                                        'accessorial')
                                    vals = {
                                        'name': data['carrierName'],
                                        'code': data['scac'],
                                        'total_price': data['totalPrice'],
                                        'sale_id': self.id,
                                        # 'accessorial_name':
                                        #     accessorial['name'],
                                        # 'accessorial_type':
                                        #     accessorial['accessorialType'],
                                        # 'accessorial_price':
                                        #     accessorialcharges['charge'],
                                    }
                            vals.update(
                                {'service_type': data['serviceType'], 'service': data['service']})
                            self.env['fetch.carrier.rates'].create(vals)
                        else:
                            self.env['fetch.carrier.rates'].create({
                                'name': data['carrierName'],
                                'code': data['scac'],
                                'total_price': data['totalPrice'],
                                'sale_id': self.id,
                                'service_type': data['serviceType'],
                                'service': data['service'],
                            })
        if record and record.get('errors'):
            raise MissingError(_('%s') % record['errors'][0])

        self.action_fetch_carrier_rates()

    def action_fetch_carrier_rates(self):
        self.ensure_one()
        action = self.env.ref(
            'kuebix_connector.view_fetch_carrier_rates_action').read()[0]
        action['domain'] = [('sale_id', '=', self.id)]
        action['view_mode'] = 'tree,form'
        action['views'] = [(k, v) for k, v in action['views'] if
                           v in ['tree', 'form']]
        return action

    def _get_carrier_count(self):
        for order in self:
            order.carrier_count = self.env['fetch.carrier.rates'].search_count(
                [('sale_id', '=', order.id)])
