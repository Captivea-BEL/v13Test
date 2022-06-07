# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
DOC_PREFIX_PO = '850'  # Prefix for Purchase Order Document
DOC_PREFIX_POC = '860'  # Prefix for Purchase Order Change Document
DOC_PREFIX_POA = '855'  # Prefix for Purchase Order Aknowledgment Document
DOC_PREFIX_ASN = '856'  # Prefix for Advanced Ship Notice Document
DOC_PREFIX_BIL = '810'  # Prefix for Invoice Document
DOC_PREFIX_INV = '846'  # Prefix for Inventory Document

POA_FIELDS = ['TRANSACTION ID', 'ACCOUNTING ID', 'PURPOSE', 'TYPE STATUS',
              'PO #', 'PO DATE', 'RELEASE NUMBER', 'REQUEST REFERENCE NUMBER',
              'CONTRACT NUMBER', 'SELLING PARTY NAME',
              'SELLING PARTY ADDRESS 1', 'SELLING PARTY ADDRESS 2',
              'SELLING PARTY CITY', 'SELLING PARTY STATE', 'SELLING PARTY ZIP',
              'ACCOUNT NUMBER - VENDOR NUMBER', 'WAREHOUSE ID', 'LINE #',
              'PO LINE #', 'VENDOR PART #', 'UPC', 'SKU', 'QTY', 'UOM',
              'PRICE', 'SCHEDULED DELIVERY DATE', 'SCHEDULED DELIVERY TIME',
              'ESTIMATED DELIVERY DATE', 'ESTIMATED DELIVERY TIME',
              'PROMISED DATE', 'PROMISED TIME', 'STATUS', 'STATUS QTY',
              'STATUS UOM']

ASN_FIELDS = ['TRANSACTION TYPE', 'ACCOUNTING ID', 'SHIPMENT ID', 'SCAC',
              'CARRIER PRO NUMBER', 'BILL OF LADING', 'SCHEDULED DELIVERY',
              'SHIP DATE', 'SHIP TO NAME', 'SHIP TO ADDRESS - LINE ONE',
              'SHIP TO ADDRESS - LINE TWO', 'SHIP TO CITY', 'SHIP TO STATE',
              'SHIP TO ZIP', 'SHIP TO COUNTRY', 'SHIP TO ADDRESS CODE',
              'SHIP VIA', 'SHIP TO TYPE', 'PACKAGING TYPE', 'GROSS WEIGHT',
              'GROSS WEIGHT UOM', 'NUMBER OF CARTONS SHIPPED',
              'CARRIER TRAILER NUMBER', 'TRAILER INITIAL', 'SHIP FROM NAME',
              'SHIP FROM ADDRESS - LINE ONE', 'SHIP FROM ADDRESS - LINE TWO',
              'SHIP FROM CITY', 'SHIP FROM STATE', 'SHIP FROM ZIP',
              'SHIP FROM COUNTRY', 'SHIP FROM ADDRESS CODE', 'VENDOR NUMBER',
              'DC CODE', 'TRANSPORTATION METHOD', 'PRODUCT GROUP', 'STATUS',
              'TIME SHIPPED', 'PO NUMBER', 'PO DATE', 'INVOICE NUMBER',
              'ORDER WEIGHT', 'STORE NAME', 'STORE NUMBER', 'MARK FOR CODE',
              'DEPARTMENT NUMBER', 'ORDER LADING QUANTITY', 'PACKAGING TYPE',
              'UCC-128', 'PACK SIZE', 'INNER PACK PER OUTER PACK',
              'PACK HEIGHT', 'PACK WIDTH', 'PACK WEIGHT',
              'QTY OF UPCS WITHIN PACK', 'UOM OF UPCS', 'STORE NAME',
              'STORE NUMBER', 'LINE NUMBER', 'VENDOR PART NUMBER',
              'BUYER PART NUMBER', 'UPC NUMBER', 'ITEM DESCRIPTION',
              'QUANTITY SHIPPED', 'UOM', 'QUANTITY ORDERED', 'UNIT PRICE',
              'PACK SIZE', 'PACK UOM', 'INNER PACKS PER OUTER PACK']
import time
import pytz
import csv
import pysftp
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import Warning
from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = ['sale.order']

    file_ref = fields.Char()
    x_edi_reference = fields.Char('EDI Reference', copy=False, store=False, compute='_compute_ref')
    x_edi_accounting_id = fields.Char('Trading Partner ID', copy=False, compute='_compute_sale_edi_values', store=False)
    x_edi_store_number = fields.Char('Store number', related='partner_shipping_id.x_edi_store_number', copy=False)
    x_edi_flag = fields.Boolean('EDI Flag', copy=False)
    poack_created = fields.Boolean(string="Acknowledged?", copy=False)
    customer_po_ref = fields.Many2one('setu.edi.log', copy=False)
    poack_ref = fields.Many2one('setu.edi.log', copy=False)

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        self.order_line.set_po_line_number()
        return res

    @api.depends('client_order_ref')
    def _compute_ref(self):
        for sale in self:
            sale.x_edi_reference = sale.client_order_ref

    @api.depends('partner_id.x_edi_accounting_id', 'partner_shipping_id.x_edi_store_number')
    def _compute_sale_edi_values(self):
        for record in self:
            record.x_edi_accounting_id = record.partner_id and record.partner_id.x_edi_accounting_id or ''
            record.x_edi_store_number = record.partner_shipping_id and record.partner_shipping_id.x_edi_store_number or ''

    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        if not res.x_edi_accounting_id:
            res._compute_sale_edi_values()
        return res

    def create_poack_export_log_id(self):
        """
        Will create 855 type of log.

        @return: log_id: log_id of sale_id.
        """
        log_id = self.env['setu.edi.log'].create({
            'po_number': self.client_order_ref,
            'type': 'export',
            'document_type': '855',
            'sale_id': self.id
        })
        export_log = self.env['setu.poack.export.log.line']
        user_tz = pytz.timezone(self.env.user.tz or 'utc')
        for line in self.order_line:
            export_log.create({
                'accounting_id': self.x_edi_accounting_id,
                'po_number': self.client_order_ref,
                'vendor_part': line.product_id.default_code,
                'po_date': str(self.date_order.astimezone(user_tz).date()) or str(
                    self.customer_po_ref.po_date),
                'company_id': self.company_id.id,
                'x_edi_po_line_number': line.x_edi_po_line_number,
                'product_template_id': line.product_template_id.id,
                'qty': line.po_log_line_id.quantity,
                'uom': line.po_log_line_id.uom,
                'price_unit': line.price_unit,
                'commitment_date': self.commitment_date and str(self.commitment_date.astimezone(user_tz).date()),
                'x_edi_status': line.x_edi_status,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_uom.name,
                'edi_log_id': log_id.id,
                'line_num': line.x_edi_po_line_number,
                'upc_num': line.product_id.barcode or line.upc_num
            })
        return log_id

    def create_poack_export_log(self, sftp):
        """
        Will create POACK log.
        @param sftp: sftp instance.
        @return:
        """
        log_id = self.create_poack_export_log_id()
        self.poack_ref = log_id
        res = self.poack_export(sftp)
        if res:
            log_id.status = 'success'
        else:
            log_id.status = 'fail'
        return log_id

    def poack_export(self, sftp):
        """
        Will upload 855 .csv file on sftp server.
        @param sftp: sftp instance
        @return: True or False
        """
        DOC_PREFIX_POA = '855'
        log_id = self.poack_ref
        company = self.company_id
        sftp_conf = self.env['setu.sftp'].search([('company_id', '=', company.id), ('instance_active', '=', True)])
        ftpdpath = sftp_conf['ftp_poack_dpath']

        file_name = '/tmp/' + str(DOC_PREFIX_POA) + '_' + str(self.client_order_ref) + str(self.partner_id.name) + \
                    '_' + '.csv'  # TO DO COMPLETE FILE NAME WITH CUSTOMER NAME
        with open(file_name, 'w+') as file_pointer:
            cvs_rows = []
            writer = csv.DictWriter(file_pointer, fieldnames=POA_FIELDS)
            writer.writeheader()
            for row in log_id.edi_855_log_lines:
                cvs_rows.append({
                    'TRANSACTION ID': DOC_PREFIX_POA,
                    'ACCOUNTING ID': row.accounting_id,
                    'PURPOSE': 'null',  # ASK TIM FOR VALUE
                    'TYPE STATUS': 'null',
                    'PO #': row.po_number,
                    'PO DATE': row.po_date,
                    'RELEASE NUMBER': 'null',
                    'REQUEST REFERENCE NUMBER': row.po_number,
                    'CONTRACT NUMBER': 'null',
                    'SELLING PARTY NAME': company.name,
                    'SELLING PARTY ADDRESS 1': company.street and
                                               company.street or 'null',
                    'SELLING PARTY ADDRESS 2': company.street2 and
                                               company.street2 or 'null',
                    'SELLING PARTY CITY': company.city and
                                          company.city or 'null',
                    'SELLING PARTY STATE': company.state_id and
                                           company.state_id.name or 'null',
                    'SELLING PARTY ZIP': company.zip and
                                         company.zip or 'null',

                    'ACCOUNT NUMBER - VENDOR NUMBER': self.partner_id.edi_vendor_number or self.partner_shipping_id.edi_vendor_number,
                    'WAREHOUSE ID': 'null',
                    'LINE #': 'null',
                    'PO LINE #': row.line_num and
                                 row.line_num or 'null',
                    'VENDOR PART #': row.vendor_part or 'null',

                    'UPC': row.upc_num and
                           row.upc_num or 'null',
                    'SKU': 'null',
                    'QTY': row.qty and row.qty or 'null',
                    'UOM': row.uom and row.uom or 'null',
                    'PRICE': row.price_unit and row.price_unit or 0.0,
                    'SCHEDULED DELIVERY DATE': row.commitment_date,
                    'SCHEDULED DELIVERY TIME': 'null',
                    'ESTIMATED DELIVERY DATE': 'null',
                    'ESTIMATED DELIVERY TIME': 'null',
                    'PROMISED DATE': 'null',
                    'PROMISED TIME': 'null',
                    'STATUS': row.x_edi_status,
                    'STATUS QTY': row.product_uom_qty,
                    'STATUS UOM': row.product_uom
                })
            writer.writerows(cvs_rows)
            file_pointer.close()
            if sftp:
                sftp.cwd(ftpdpath)
                sftp.put(file_name, ftpdpath + '/' + str(DOC_PREFIX_POA) + '_' + str(self.client_order_ref) + '_' + str(
                    self.name) + '.csv')
                self.poack_created = True
                log_id.create_date = date.today()
                return True
            return False

    def get_edi_status(self):
        """
        This method will set edi status to order_lines.
        'accept' or 'reject'.
        @return:
        """
        lines = self.order_line
        for line in lines:
            if line.product_uom_qty > 0:
                line.x_edi_status = 'accept'
            else:
                line.x_edi_status = 'reject'

    def action_confirm(self):
        """
        Will create 855 POACK when sale order is confirmed.
        It will assign edi values to pickings that are created.
        @return:
        """
        for record in self:
            if record.x_edi_accounting_id and record.partner_id.edi_855:
                record.get_edi_status()
        pop_error = False
        for rec in self:
            if not rec.x_edi_accounting_id and rec.partner_id.x_edi_flag and rec.partner_id.edi_855:
                pop_error = True
                if len(self) == 1:
                    raise Warning(
                        _("Please make sure the Accounting ID is properly set on the Customer so the PO Acknowledgment can be sent to the Customer"))
        res = super(SaleOrder, self).action_confirm()
        if res and not pop_error:
            for record in self:
                acc_id = record.x_edi_accounting_id
                if acc_id and record.partner_id.edi_855 and not record.poack_created:
                    record.creat_poack_log_and_poack_export()
                pickings = record.picking_ids
                for pick in pickings:
                    pick.write(
                        {'x_edi_accounting_id': acc_id,
                         # 'ship_from_warehouse': self.env['stock.warehouse'].search(
                         # [('wh_output_stock_loc_id', '=', pick.location_id.id)]),
                         # 'edi_vendor_number': pick.partner_id.parent_id.edi_vendor_number if pick.partner_id.parent_id else pick.partner_id.edi_vendor_number,
                         'edi_vendor_number': pick.sale_id.partner_id.edi_vendor_number if pick.sale_id else False,
                         'x_edi_ship_to_type': self.partner_shipping_id.x_edi_ship_to_type}
                        )
        return res

    def creat_poack_log_and_poack_export(self):
        """
        Main method to create 855 log and export 855 .csv file on sftp server.
        @return: log_ids:
        """
        log_ids = self.env['setu.edi.log']
        sftp_conf = self.env['setu.sftp'].search(
            [('company_id', '=', self.company_id.id),
             ('instance_active', '=', True)])
        if sftp_conf:
            sftp, status = sftp_conf.test_connection()
            for sale in self:
                if sftp:
                    log_ids |= sale.create_poack_export_log(sftp)
                else:
                    log_id = self.env['setu.edi.log'].create({
                        'po_number': sale.client_order_ref,
                        'type': 'export',
                        'document_type': '855',
                        'status': 'fail',
                        'exception': status,
                        'sale_id': sale.id
                    })
                    sale.poack_ref = log_id
                    log_ids |= log_id
            if sftp:
                sftp.close()
            return log_ids


class SaleAdvPayinv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def create_invoices(self):
        """
        This inherited method will set edi values to invoice which is created.
        @return:
        """
        res = super(SaleAdvPayinv, self).create_invoices()
        sale = self.env['sale.order'].browse(self.env.context.get('active_id'))
        sale_cr_invoices = sale.invoice_ids.filtered(lambda inv: not inv.reversed_entry_id)
        sale_cr_invoices.x_edi_accounting_id = sale.x_edi_accounting_id
        sale_cr_invoices.x_studio_edi_reference = sale.client_order_ref
        sale_cr_invoices.x_edi_store_number = sale.x_edi_store_number
        sale_cr_invoices.x_edi_ship_to_type = sale.partner_shipping_id.x_edi_ship_to_type
        sale_cr_invoices.x_edi_transaction_type = 'DR'
        return res
