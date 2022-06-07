from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # weight_uom = fields.Selection([
    #     ('lb', 'LB'),
    #     ('kg', 'KG')], string='Weight Unit of Measure', default='lb')
    # length_uom = fields.Selection([
    #     ('in', 'IN'),
    #     ('cm', 'CM'),
    #     ('ft', 'FT'),
    #     ('m', 'M')], string='Length Unit of Measure', default='in')
    freight_class = fields.Selection([('60', '60'),
                                      ('77.5', '77.5'), ('125', '125')],
                                     string='Freight Class', default='77.5')
    # paymenttype = fields.Selection([
    #     ('Inbound Collect', 'Inbound Collect'),
    #     ('Outbound Collect', 'Outbound Collect'),
    #     ('Outbound Prepaid', 'Outbound Prepaid'),
    #     ('Third Party', 'Third Party'),
    #     ('Third Party Collect', 'Third Party Collect'),
    #     ('Vendor Delivered', 'Vendor Delivered')],
    #     string='Payment Type', default='Outbound Prepaid')

    hutype = fields.Selection([
        ('bag', 'Bag(s)'),
        ('box', 'Box(es)'),
        ('bundle', 'Bundle(s)'),
        ('carton', 'Carton(s)'),
        ('container', 'Container(s)'),
        ('crate', 'Crate(s)'),
        ('cylinder', 'Cylinder(s)'),
        ('drum', 'Drum(s)'),
        ('pallet', 'Pallet(s)'),
        ('roll', 'Roll(s)'),
        ('skid', 'Skid(s)'),
        ('tank', 'Tank(s)'),
        ('tube', 'Tube(s)')],
        string='huType', default='')
