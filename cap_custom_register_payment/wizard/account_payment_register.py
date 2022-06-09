

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'out_receipt': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
    'in_receipt': 'supplier',
}

class payment_register(models.TransientModel):
    
    _inherit = "account.payment.register"
    
    # move_line_ids = fields.One2many("account.move.line","payment_register_id",string="Journal Items")
    move_line_ids = fields.Many2many('account.move.line', 'account_move_line_payment_rel_transient', 'payment_id', 'move_line_id', string="Journal Items", copy=False, readonly=True)
    amount = fields.Monetary(string='Amount', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    group_payment = fields.Boolean(help="Only one payment will be created by partner (bank)/ currency.", default=True)
    invoice_bill_ids = fields.Many2many("unique.invoice.bills",'unique_invoice_bills_acc_pay_reg_rel','invoice_bill_id','account_payment_register_id',"Unique Invoices/Bills")
    
    invoice_ids = fields.Many2many('account.move', 'account_invoice_payment_rel_transient', 'payment_id', 'invoice_id', string="Invoices", copy=False)
    payment_type = fields.Selection([('outbound', 'Send Money'), ('inbound', 'Receive Money'), ('transfer', 'Internal Transfer')], string='Payment Type', required=True, readonly=True)#, states={'draft': [('readonly', False)]}
    company_id = fields.Many2one('res.company', related='journal_id.company_id', string='Company', readonly=True)
    payment_difference = fields.Monetary(compute='_compute_payment_difference', readonly=True)
    payment_difference_handling = fields.Selection([('open', 'Keep open'), ('reconcile', 'Mark invoice as fully paid')], default='open', string="Payment Difference Handling", copy=False)
    writeoff_account_id = fields.Many2one('account.account', string="Difference Account", domain="[('deprecated', '=', False), ('company_id', '=', company_id)]", copy=False)
    writeoff_label = fields.Char(
        string='Journal Item Label',
        help='Change label of the counterpart that will hold the payment difference',
        default='Write-Off')
    
    communication = fields.Char(string='Payment Reference')
    apply_discount = fields.Boolean("Apply Discount")
    
    # invoice_bill_ids = fields.Many2many("unique.invoice.bills",'unique_invoice_bills_acc_pay_reg_rel','invoice_bill_id','account_payment_register_id',"Unique Invoices/Bills")

    @api.onchange('payment_date')
    def onchange_payment_date(self):
        total_amount = 0.0
        for inv in self.invoice_ids:
            if inv.early_terms_date:
                if self.payment_date <= inv.early_terms_date:
                    total_amount += inv.early_terms_total_due
                else:
                    total_amount += inv.amount_residual
            else:
                total_amount += inv.amount_residual
        self.amount = total_amount

    @api.onchange('apply_discount')
    def onchange_apply_discount(self):
        if self.apply_discount:
            self.amount = sum(self.invoice_ids.mapped('early_terms_total_due'))
        else:
            self.amount = sum(self.invoice_ids.mapped('amount_residual'))
        # total_amount = self.amount
        # if self.apply_discount == True:
        #     total_amount = 0.0
        #     for inv_bill in self.invoice_bill_ids:
        #         total_amount += inv_bill.total_amount
        #
        # self.amount = total_amount
    
    
    @api.onchange('invoice_bill_ids')
    def onchange_invoice_bill_ids(self):
        total_amount = 0.0
        for inv_bill in self.invoice_bill_ids:
            total_amount += inv_bill.total_amount
        self.amount = total_amount
    
    @api.depends('invoice_ids', 'amount', 'payment_date', 'currency_id', 'payment_type')
    def _compute_payment_difference(self):
        draft_payments = self.filtered(lambda p: p.invoice_ids) #and p.state == 'draft'
        total_actual_amount = 0.0
        if len(self.invoice_ids) == 1:
            total_actual_amount = sum(self.invoice_ids.mapped('amount_total'))
        elif len(self.invoice_ids) > 1:
            for inv in self.invoice_ids:
                total_actual_amount += inv.amount_total
        for pay in draft_payments:
            payment_amount = -pay.amount if pay.payment_type == 'outbound' else pay.amount
            if total_actual_amount != pay.amount:
                if pay.payment_type == 'inbound':
                    pay.payment_difference = total_actual_amount - pay.amount
                if pay.payment_type == 'outbound':
                    pay.payment_difference = total_actual_amount - pay.amount
                    pay.payment_difference = -(pay.payment_difference)
            if total_actual_amount == pay.amount:
                pay.payment_difference = 0.0
        (self - draft_payments).payment_difference = 0

    
    def _prepare_payment_vals(self, invoices):
        res = super(payment_register, self)._prepare_payment_vals(invoices)
        # if res.get('amount') != self.amount and len(self.invoice_bill_ids) == 1:
        #     res['amount'] = self.amount
        if self.communication:
            res['communication'] = self.communication
        return res

    # override method to add custom code for doing batch payment.
    def create_payments(self):
        '''Create payments according to the invoices.
        Having invoices with different commercial_partner_id or different type
        (Vendor bills with customer invoices) leads to multiple payments.
        In case of all the invoices are related to the same
        commercial_partner_id and have the same type, only one payment will be
        created.

        :return: The ir.actions.act_window to show created payments.
        '''
        Payment = self.env['account.payment']
        payment_vals = self.get_payments_vals()
        unique_invoice_bill_ids = self.invoice_bill_ids
        for payment in payment_vals:
            if payment['communication']:
                communication_name_list = payment['communication'].split(' ')
                invoice = self.env['account.move'].search([('name','in',communication_name_list)], limit=1)
                if invoice:
                    if len(unique_invoice_bill_ids) > 1:
                        for uniq_inv_bill in unique_invoice_bill_ids:
                            if invoice in uniq_inv_bill.account_move_ids:
                                payment['amount'] = uniq_inv_bill.total_amount
        payments = Payment.create(payment_vals)
        payments.with_context({'payment_difference_handling': self.payment_difference_handling, 'writeoff_account_id': self.writeoff_account_id}).post()
        for pmnt in payments:
            for inv in pmnt.invoice_ids:
                inv.invoice_payment_ref = pmnt.communication
        action_vals = {
            'name': _('Payments'),
            'domain': [('id', 'in', payments.ids), ('state', '=', 'posted')],
            'res_model': 'account.payment',
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
        if len(payments) == 1:
            action_vals.update({'res_id': payments[0].id, 'view_mode': 'form'})
        else:
            action_vals['view_mode'] = 'tree,form'
        return action_vals
    
    @api.model
    def default_get(self, fields):
        rec = super(payment_register, self).default_get(fields)
        if rec['invoice_ids']:
            invoices = rec['invoice_ids']
        if invoices:
            inv_list = []
            for inv in invoices:
                inv_list = inv_list + inv[2]
            invoice_line_ids = self.env['account.move'].browse(inv_list).mapped('line_ids')
            invoice_ids = self.env['account.move'].browse(inv_list)
        
        available_lines = self.env['account.move.line']
        for line in invoice_line_ids:
            if line.move_id.state != 'posted':
                    raise UserError(_("You can only register payment for posted journal entries."))

            if line.account_internal_type not in ('receivable', 'payable'):
                continue
            if line.currency_id:
                if line.currency_id.is_zero(line.amount_residual_currency):
                    continue
            else:
                if line.company_currency_id.is_zero(line.amount_residual):
                    continue
            available_lines |= line
        unique_partner_list = []
        for line in available_lines:
            if line.partner_id.id not in unique_partner_list:
                unique_partner_list.append(line.partner_id.id)
        partner_dict = {}
        for partner_id in unique_partner_list:
            companylist=[]
            recordlist=[]
            payment_amount = 0
            for line in available_lines:
                if line.partner_id.id == partner_id:
                    recordlist.append(line.move_id.id)
                    payment_amount += ((line.credit if line.debit == 0 else line.debit) or (line.debit if line.credit == 0 else line.credit))
                    if line.company_id not in companylist:
                        companylist.append(line.company_id.id)
            partner_dict.update({partner_id:{'company_list': companylist, 'record_list': recordlist, 'payment_amount': payment_amount}})
        unique_invoice_bills_ids = self.env['unique.invoice.bills']
        for k, v in partner_dict.items():
            # for comp in :
            move_ids = self.env['account.move'].search([('id', 'in', v['record_list']),('company_id','in',v['company_list'])])
            total_amount = 0.0
            for mv in move_ids:
                if mv.invoice_payment_term_id:
                    total_amount += mv.early_terms_total_due
                else:
                    total_amount += mv.amount_total
            unique_inv_bill_id = self.env['unique.invoice.bills'].create({'partner_id': k, 'account_move_ids': [(6,0,move_ids.ids)], 'company_ids': [(6,0,v['company_list'])], 'total_amount': total_amount})
            unique_invoice_bills_ids |= unique_inv_bill_id
        total_amount = 0.0
        actual_total_amount = 0.0
        for inv in invoice_ids:
            if inv.early_terms_total_due and inv.amount_total and inv.early_terms_total_due != inv.amount_total:
                total_amount += inv.early_terms_total_due
            elif inv.early_terms_total_due and inv.amount_total and inv.early_terms_total_due == inv.amount_total:
                total_amount += inv.amount_total

        writeoff_account = self.env['account.account']
        mapped_invoices = invoice_ids.mapped('type')
        writeoff_account_id = False
        if 'in_invoice' in mapped_invoices or 'in_refund' in mapped_invoices:
            total_amount = -(total_amount)
            ap_discount_account = self.env['ir.config_parameter'].sudo().get_param('cap_custom_register_payment.default_ap_discount_account')
            if ap_discount_account:
                writeoff_account_id = writeoff_account.browse(ap_discount_account).id
        elif 'out_invoice' in mapped_invoices or 'out_refund' in mapped_invoices:
            total_amount = total_amount
            ar_discount_account = self.env['ir.config_parameter'].sudo().get_param('cap_custom_register_payment.default_ar_discount_account')
            if ar_discount_account:
                writeoff_account_id = writeoff_account.browse(ar_discount_account).id
        
        communication = ''
        if False not in invoice_ids.mapped('invoice_payment_ref'):
            communication = ' '.join(invoice_ids.mapped('invoice_payment_ref'))
        rec.update({'move_line_ids': [(6,0,available_lines.ids)], 'amount': abs(total_amount),'payment_type': 'inbound' if total_amount > 0 else 'outbound', 'invoice_bill_ids': [(6, 0, unique_invoice_bills_ids.ids)], 'payment_difference_handling': 'reconcile', 'communication': communication, 'writeoff_account_id': int(writeoff_account_id) if writeoff_account_id else False})
        return rec


class UniqueInvoiceBill(models.TransientModel):
    
    _name = "unique.invoice.bills"
    _description = 'Unique Invoice/Bill'
    
    partner_id = fields.Many2one("res.partner")
    account_move_ids = fields.Many2many("account.move",'unique_invoice_bill_account_move_rel','unique_inv_bill_id','account_move_id', "Moves")
    company_id = fields.Many2one("res.company", string="Company")
    company_ids = fields.Many2many("res.company", 'res_company_unique_invoice_bills_rel','company_id','unique_invoice_bills_id', string="Companies")
    total_amount = fields.Float(string="Amount")
    customer_payment_method = fields.Many2one(related="partner_id.customer_payment_method", string="Customer Payment Method", readonly=False)
    vendor_payment_method = fields.Many2one(related="partner_id.vendor_payment_method", string="Vendor Payment Method", readonly=False)

