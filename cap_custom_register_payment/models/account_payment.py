

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AccountPayment(models.Model):

    _inherit = "account.payment"
    
    apply_discount = fields.Boolean("Apply Discount")
    
    invoice_ids = fields.Many2many('account.move', 'account_invoice_payment_rel', 'payment_id', 'invoice_id', string="Invoices", copy=False,
                                   help="""Technical field containing the invoice for which the payment has been generated.
                                   This does not especially correspond to the invoices reconciled with the payment,
                                   as it can have been generated first, and reconciled later""")

    communication = fields.Char(string='Payment Reference', readonly=True, states={'draft': [('readonly', False)]})

    @api.onchange('payment_date')
    def onchange_payment_date(self):
        total_amount = 0.0
        for inv in self.invoice_ids:
            if inv.early_terms_date and inv.invoice_date:
                if inv.invoice_date < self.payment_date and self.payment_date < inv.early_terms_date:
                    total_amount += inv.early_terms_total_due
                else:
                    total_amount += inv.amount_residual
            else:
                total_amount += inv.amount_residual
        self.amount = total_amount

    def post(self):
        res = super(AccountPayment, self).post()
        for rec in self:
            for inv in rec.invoice_ids:
                inv.invoice_payment_ref = rec.communication
        return res
    
    @api.onchange('apply_discount')
    def onchange_apply_discount(self):
        draft_payments = self.filtered(lambda p: p.invoice_ids and p.state == 'draft')
        for pay in draft_payments:
            if pay.apply_discount == True:
                pay.amount = pay._compute_payment_amount(pay.invoice_ids, pay.currency_id, pay.journal_id, pay.payment_date)
                pay.amount = abs(pay.amount)
                
    
    def action_register_payment(self):
        res = super(AccountPayment, self).action_register_payment()
        if self._context.get('active_ids'):
            move_partner_ids = self.env['account.move'].browse(self._context.get('active_ids')).mapped('partner_id')
            if len(move_partner_ids.ids) > 1:
                raise ValidationError(_("You cannot select multiple customers for multiple register payment !"))
        return res
    
    @api.model
    def default_get(self, default_fields):
        rec = super(AccountPayment, self).default_get(default_fields)
        invoices = self.env['account.move']
        if rec.get('invoice_ids'):
            invoices = rec.get('invoice_ids')
        # print ("invoices --->>", invoices)
        writeoff_account_id = False
        if invoices:
            inv_list = []
            for inv in invoices:
                inv_list = inv_list + inv[2]
            invoice_line_ids = self.env['account.move'].browse(inv_list).mapped('line_ids')
            invoices = self.env['account.move'].browse(inv_list)
        
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
            writeoff_account = self.env['account.account']
            if 'out_invoice' in invoices.mapped('type') or 'out_refund' in invoices.mapped('type'):
                ar_discount_account = self.env['ir.config_parameter'].sudo().get_param('cap_custom_register_payment.default_ar_discount_account')
                if ar_discount_account:
                    writeoff_account_id = writeoff_account.browse(ar_discount_account).id
            elif 'in_invoice' in invoices.mapped('type') or 'in_refund' in invoices.mapped('type'):
                ap_discount_account = self.env['ir.config_parameter'].sudo().get_param('cap_custom_register_payment.default_ap_discount_account')
                if ap_discount_account:
                    writeoff_account_id = writeoff_account.browse(ap_discount_account).id
            print ("writeoff_account_id --->>", writeoff_account_id)
        rec.update({'payment_difference_handling': 'reconcile', 'writeoff_account_id': int(writeoff_account_id) if writeoff_account_id else False})
        return rec
    
    def _prepare_payment_moves(self):
        ''' Prepare the creation of journal entries (account.move) by creating a list of python dictionary to be passed
        to the 'create' method.

        Example 1: outbound with write-off:

        Account             | Debit     | Credit
        ---------------------------------------------------------
        BANK                |   900.0   |
        RECEIVABLE          |           |   1000.0
        WRITE-OFF ACCOUNT   |   100.0   |

        Example 2: internal transfer from BANK to CASH:

        Account             | Debit     | Credit
        ---------------------------------------------------------
        BANK                |           |   1000.0
        TRANSFER            |   1000.0  |
        CASH                |   1000.0  |
        TRANSFER            |           |   1000.0

        :return: A list of Python dictionary to be passed to env['account.move'].create.
        '''
        all_move_vals = []
        for payment in self:
            company_currency = payment.company_id.currency_id
            move_names = payment.move_name.split(payment._get_move_name_transfer_separator()) if payment.move_name else None
            if self._context.get('writeoff_account_id'):
                payment.writeoff_account_id = self._context.get('writeoff_account_id')
            # Compute amounts.
            if payment.payment_difference > 0:
                write_off_amount = payment.payment_difference_handling == 'reconcile' and -payment.payment_difference or 0.0
            elif payment.payment_difference <= 0:
                write_off_amount = payment.payment_difference_handling == 'reconcile' and payment.payment_difference or 0.0
            if payment.payment_type in ('outbound', 'transfer'):
                counterpart_amount = payment.amount
                write_off_amount = -(write_off_amount)
                liquidity_line_account = payment.journal_id.default_debit_account_id
            else:
                counterpart_amount = -payment.amount
                liquidity_line_account = payment.journal_id.default_credit_account_id
            # Manage currency.
            if payment.currency_id == company_currency:
                # Single-currency.
                balance = counterpart_amount
                write_off_balance = write_off_amount
                counterpart_amount = write_off_amount = 0.0
                currency_id = False
            else:
                # Multi-currencies.
                balance = payment.currency_id._convert(counterpart_amount, company_currency, payment.company_id, payment.payment_date)
                write_off_balance = payment.currency_id._convert(write_off_amount, company_currency, payment.company_id, payment.payment_date)
                currency_id = payment.currency_id.id
            # Manage custom currency on journal for liquidity line.
            if payment.journal_id.currency_id and payment.currency_id != payment.journal_id.currency_id:
                # Custom currency on journal.
                if payment.journal_id.currency_id == company_currency:
                    # Single-currency
                    liquidity_line_currency_id = False
                else:
                    liquidity_line_currency_id = payment.journal_id.currency_id.id
                liquidity_amount = company_currency._convert(
                    balance, payment.journal_id.currency_id, payment.company_id, payment.payment_date)
            else:
                # Use the payment currency.
                liquidity_line_currency_id = currency_id
                liquidity_amount = counterpart_amount

            # Compute 'name' to be used in receivable/payable line.
            rec_pay_line_name = ''
            if payment.payment_type == 'transfer':
                rec_pay_line_name = payment.name
            else:
                if payment.partner_type == 'customer':
                    if payment.payment_type == 'inbound':
                        rec_pay_line_name += _("Customer Payment")
                    elif payment.payment_type == 'outbound':
                        rec_pay_line_name += _("Customer Credit Note")
                elif payment.partner_type == 'supplier':
                    if payment.payment_type == 'inbound':
                        rec_pay_line_name += _("Vendor Credit Note")
                    elif payment.payment_type == 'outbound':
                        rec_pay_line_name += _("Vendor Payment")
                if payment.invoice_ids:
                    rec_pay_line_name += ': %s' % ', '.join(payment.invoice_ids.mapped('name'))

            # Compute 'name' to be used in liquidity line.
            if payment.payment_type == 'transfer':
                liquidity_line_name = _('Transfer to %s') % payment.destination_journal_id.name
            else:
                liquidity_line_name = payment.name

            # ==== 'inbound' / 'outbound' ====
            move_vals = {
                'date': payment.payment_date,
                'ref': payment.communication,
                'journal_id': payment.journal_id.id,
                'currency_id': payment.journal_id.currency_id.id or payment.company_id.currency_id.id,
                'partner_id': payment.partner_id.id,
                'line_ids': [
                    # Receivable / Payable / Transfer line.
                    (0, 0, {
                        'name': rec_pay_line_name,
                        'amount_currency': counterpart_amount + write_off_amount if currency_id else 0.0,
                        'currency_id': currency_id,
                        'debit': balance + write_off_balance > 0.0 and balance + write_off_balance or 0.0,
                        'credit': balance + write_off_balance < 0.0 and -balance - write_off_balance or 0.0,
                        'date_maturity': payment.payment_date,
                        'partner_id': payment.partner_id.commercial_partner_id.id,
                        'account_id': payment.destination_account_id.id,
                        'payment_id': payment.id,
                    }),
                    # Liquidity line.
                    (0, 0, {
                        'name': liquidity_line_name,
                        'amount_currency':-liquidity_amount if liquidity_line_currency_id else 0.0,
                        'currency_id': liquidity_line_currency_id,
                        'debit': balance < 0.0 and -balance or 0.0,
                        'credit': balance > 0.0 and balance or 0.0,
                        'date_maturity': payment.payment_date,
                        'partner_id': payment.partner_id.commercial_partner_id.id,
                        'account_id': liquidity_line_account.id,
                        'payment_id': payment.id,
                    }),
                ],
            }
            if write_off_balance:
                # Write-off line.
                move_vals['line_ids'].append((0, 0, {
                    'name': payment.writeoff_label,
                    'amount_currency':-write_off_amount,
                    'currency_id': currency_id,
                    'debit': write_off_balance < 0.0 and -write_off_balance or 0.0,
                    'credit': write_off_balance > 0.0 and write_off_balance or 0.0,
                    'date_maturity': payment.payment_date,
                    'partner_id': payment.partner_id.commercial_partner_id.id,
                    'account_id': payment.writeoff_account_id.id,
                    'payment_id': payment.id,
                }))
            if move_names:
                move_vals['name'] = move_names[0]

            all_move_vals.append(move_vals)

            # ==== 'transfer' ====
            if payment.payment_type == 'transfer':
                journal = payment.destination_journal_id

                # Manage custom currency on journal for liquidity line.
                if journal.currency_id and payment.currency_id != journal.currency_id:
                    # Custom currency on journal.
                    liquidity_line_currency_id = journal.currency_id.id
                    transfer_amount = company_currency._convert(balance, journal.currency_id, payment.company_id, payment.payment_date)
                else:
                    # Use the payment currency.
                    liquidity_line_currency_id = currency_id
                    transfer_amount = counterpart_amount

                transfer_move_vals = {
                    'date': payment.payment_date,
                    'ref': payment.communication,
                    'partner_id': payment.partner_id.id,
                    'journal_id': payment.destination_journal_id.id,
                    'line_ids': [
                        # Transfer debit line.
                        (0, 0, {
                            'name': payment.name,
                            'amount_currency':-counterpart_amount if currency_id else 0.0,
                            'currency_id': currency_id,
                            'debit': balance < 0.0 and -balance or 0.0,
                            'credit': balance > 0.0 and balance or 0.0,
                            'date_maturity': payment.payment_date,
                            'partner_id': payment.partner_id.commercial_partner_id.id,
                            'account_id': payment.company_id.transfer_account_id.id,
                            'payment_id': payment.id,
                        }),
                        # Liquidity credit line.
                        (0, 0, {
                            'name': _('Transfer from %s') % payment.journal_id.name,
                            'amount_currency': transfer_amount if liquidity_line_currency_id else 0.0,
                            'currency_id': liquidity_line_currency_id,
                            'debit': balance > 0.0 and balance or 0.0,
                            'credit': balance < 0.0 and -balance or 0.0,
                            'date_maturity': payment.payment_date,
                            'partner_id': payment.partner_id.commercial_partner_id.id,
                            'account_id': payment.destination_journal_id.default_credit_account_id.id,
                            'payment_id': payment.id,
                        }),
                    ],
                }

                if move_names and len(move_names) == 2:
                    transfer_move_vals['name'] = move_names[1]

                all_move_vals.append(transfer_move_vals)
        return all_move_vals
    
    @api.depends('invoice_ids', 'amount', 'payment_date', 'currency_id', 'payment_type')
    def _compute_payment_difference(self):
        draft_payments = self.filtered(lambda p: p.invoice_ids and p.state == 'draft')
        total_actual_amount = 0.0
        if len(self.invoice_ids) >= 1:
            total_actual_amount = sum(self.invoice_ids.mapped('amount_total'))
            total_amount_residual = sum(self.invoice_ids.mapped('amount_residual'))
        for pay in draft_payments:
            payment_amount = -pay.amount if pay.payment_type == 'outbound' else pay.amount
            pay.payment_difference = pay._compute_payment_amount(pay.invoice_ids, pay.currency_id, pay.journal_id, pay.payment_date) - payment_amount
            if total_actual_amount and total_actual_amount != pay.amount and pay.payment_type == 'inbound':
                pay.payment_difference = total_actual_amount - pay.amount
            elif total_actual_amount and total_actual_amount != pay.amount and pay.payment_type == 'outbound':
                pay.payment_difference = total_actual_amount - abs(pay.amount)
                pay.payment_difference = -(pay.payment_difference)
            elif total_actual_amount == pay.amount:
                pay.payment_difference = 0.0
        (self - draft_payments).payment_difference = 0
    
    @api.model
    def _compute_payment_amount(self, invoices, currency, journal, date):
        rec = super(AccountPayment, self)._compute_payment_amount(invoices, currency, journal, date)
        super_rec = rec
        move_id = self.env['account.move'].browse(self._context.get('active_ids'))
        if len(move_id) == 1 and rec and move_id.early_terms_total_due and move_id.early_terms_total_due != rec:
            if super_rec > 0.0:
                rec = move_id.early_terms_total_due
            elif super_rec < 0.0:
                rec = -(move_id.early_terms_total_due)
        if len(move_id) > 1:
            rec = 0.0
            for mv in move_id:
                if mv.early_terms_total_due and mv.amount_total and mv.early_terms_total_due != mv.amount_total:
                    rec += mv.early_terms_total_due
                elif mv.early_terms_total_due and mv.amount_total and mv.early_terms_total_due == mv.amount_total:
                    rec += mv.amount_total
            if super_rec > 0.0:
                rec = rec
            elif super_rec < 0.0:
                rec = -(rec)
        return rec
