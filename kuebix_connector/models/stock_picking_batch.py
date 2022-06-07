
from odoo import models, fields, api, _


class StockPickingBatch(models.Model):
    
    _inherit = "stock.picking.batch"
    
    #kuebix fields
    carrier = fields.Many2one("delivery.carrier",string="Carrier")
    shipping_service = fields.Char(string="Shipping Service")
    scac = fields.Char(string="SCAC")
    tracking_ref = fields.Char(string="Tracking Reference")
    weight = fields.Float(string="Weight", compute="_compute_weight")#sum of all the weights for all the Delivery Orders
    weight_for_shipping= fields.Float(string="Weight For Shipping")
    add_tracking_numbers = fields.Text(string="Additional Tracking Numbers")
    shipment_id = fields.Char(string="Shipment ID")
    shipment_name = fields.Char(string="Shipment Name")
    kuebix_shipment_processed = fields.Boolean(string="Kuebix Shipment Processed")
    liftgate_required = fields.Selection([('yes','Yes'),('no','No')], default=False, string="Liftgate Required?")
    actual_shipment_cost = fields.Float(string="Actual Shipment Cost")
    appointment_required = fields.Selection([('yes','Yes'),('no','No')], default=False, string="Appointment Required?")
    residential_address = fields.Selection([('yes','Yes'),('no','No')], default=False, string="Residential Address?")
    
    is_shipment_id_set = fields.Boolean("Is Shipment ID?", compute="_compute_shipment_id")
    
    @api.depends("shipment_id")
    def _compute_shipment_id(self):
        for rec in self:
            if rec.shipment_id:
                rec.is_shipment_id_set = True
            else:
                rec.is_shipment_id_set = False
    
    def _compute_weight(self):
        for rec in self:
            weight = 0.0
            if rec.picking_ids:
                for pick in rec.picking_ids:
                    weight += pick.weight
                rec.weight = weight

    @api.onchange('carrier')
    def _onchange_carrier(self):
        for rec in self:
            if rec.carrier.name != "Kuebix" or "kuebix":
                rec.scac = rec.carrier.x_scac
            else:
                rec.scac = ''
    
    