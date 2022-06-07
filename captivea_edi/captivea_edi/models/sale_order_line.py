from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = ['sale.order.line']

    edi_id = fields.Many2one('setu.edi.log', string='EDI ID', copy=False)
    x_edi_mismatch = fields.Boolean('EDI Mismatch', compute='_compute_edi_price_mismatch', readonly=True)
    x_edi_po_line_number = fields.Char('PO #', readonly=True)
    x_edi_status = fields.Selection([('accept', 'Accept'), ('reject', 'Reject')], string='Status')
    upc_num = fields.Char('Barcode')
    po_log_line_id = fields.Many2one('captivea.edidocumentlog', copy=False)
    initial_product_uom_qty = fields.Float()

    def set_po_line_number(self):
        for line in self:
            if not line.po_log_line_id or not line.po_log_line_id.line_num:
                count = 1
                for id in self.ids:
                    if id < line.id:
                        count += 1

                line.x_edi_po_line_number = count


    @api.onchange('price_unit')
    def _compute_edi_price_mismatch(self):
        for rec in self:
            price = rec._get_display_price(rec.product_id)
            if price == rec.price_unit:
                rec.x_edi_mismatch = False
            else:
                rec.x_edi_mismatch = True
