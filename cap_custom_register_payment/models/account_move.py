
import datetime

from odoo import models, fields, api, _


class AccountMoveLine(models.Model):

    _inherit = "account.move.line"
    
    payment_term_discount_inclusion = fields.Boolean(string="Exclude Discount?",help="Check True if the Payment Term does NOT apply for this product/line", store=True)

class AccountMove(models.Model):
    
    _inherit = "account.move"
    
    days = fields.Integer(string="Days", compute="_compute_days")
    
    early_terms_date = fields.Date(string="Early Terms Date", compute="_compute_early_terms_date")
    
    early_terms_total_due = fields.Float(string="Early Terms Total Due", compute="_compute_early_total_due")
    
    @api.depends('invoice_payment_term_id', 'amount_residual', 'invoice_date', 'invoice_line_ids')
    def _compute_days(self):
        for record in self:
            if record.invoice_payment_term_id and record.invoice_date:
                days=datetime.date.today()-record.invoice_date
                days=days.days
                for lne in record.invoice_payment_term_id.line_ids:
                    if lne.value=='percent':
                        days=lne.days - abs(days)
                record.days = days
            else:
                record.days = False
    
    
    @api.depends('invoice_payment_term_id', 'amount_residual', 'invoice_date', 'invoice_line_ids')
    def _compute_early_terms_date(self):
        for record in self:
            if record.invoice_payment_term_id and record.invoice_date:
                days=datetime.date.today()-record.invoice_date
                days=days.days
                for lne in record.invoice_payment_term_id.line_ids:
                    if lne.value=='percent':
                        days=lne.days - abs(days)
                record.early_terms_date = datetime.date.today() + datetime.timedelta(days=days)
            else:
                record.early_terms_date = None
    
    @api.depends('invoice_payment_term_id','amount_residual','invoice_date','invoice_line_ids')
    def _compute_early_total_due(self):
        for record in self:
            perc=100
            if record.invoice_payment_term_id and record.invoice_date:
                days= record.days
                for lne in record.invoice_payment_term_id.line_ids:
                    if days <= lne.days and not days <= 0 and lne.value=='percent':
                        perc=lne.value_amount
                total_amnt = 0
                for lne in record.invoice_line_ids:
                    amnt = 0
                    if not lne.payment_term_discount_inclusion:
                        amnt=amnt+(lne.price_subtotal*perc/100)
                        if lne.tax_ids:
                            for tx in lne.tax_ids:
                                amnt += (amnt*tx.amount/100)
                        total_amnt += amnt
                    else:
                        amnt=amnt+lne.price_subtotal
                        if lne.tax_ids:
                            for tx in lne.tax_ids:
                                amnt += (amnt*tx.amount/100)
                        total_amnt += amnt
                if total_amnt > record.amount_residual:
                    total_amnt=record.amount_residual
                record.early_terms_total_due = total_amnt
            else:
                record.early_terms_total_due = False