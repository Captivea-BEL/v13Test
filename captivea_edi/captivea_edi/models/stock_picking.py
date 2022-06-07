# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import time
import re
import pytz
import csv
from datetime import date
import pysftp

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError, Warning

DOC_PREFIX_ASN = '856'  # Prefix for Advanced Ship Notice Document
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
              'PACK HEIGHT', 'PACK LENGTH', 'PACK WIDTH', 'PACK WEIGHT',
              'QTY OF UPCS WITHIN PACK', 'UOM OF UPCS', 'STORE NAME',
              'STORE NUMBER', 'LINE NUMBER', 'VENDOR PART NUMBER',
              'BUYER PART NUMBER', 'UPC NUMBER', 'ITEM DESCRIPTION',
              'QUANTITY SHIPPED', 'UOM', 'QUANTITY ORDERED', 'UNIT PRICE',
              'PACK SIZE', 'PACK UOM', 'INNER PACKS PER OUTER PACK']


class Picking(models.Model):
    _inherit = 'stock.picking'

    x_studio_edi_store_number = fields.Char('Store Number', copy=False)
    x_studio_scac = fields.Char(related='carrier_id.x_scac', copy=False)
    edi_log_ref = fields.Many2one('setu.edi.log', copy=False)
    x_edi_accounting_id = fields.Char('Trading Partner ID', copy=False)
    store_number = fields.Char('Store number', related='partner_id.x_edi_store_number', copy=False)
    x_studio_edi_packaging_type = fields.Selection([('Pallet', 'Pallet'), ('Carton', 'Carton')],
                                                   string='Packaging Type', default='Carton')
    x_edi_ship_to_type = fields.Selection([('DC', 'Warehouse Number'),
                          ('SN', 'Store Number'),
                          ('TPSO', 'Dropship TPSO'),
                          ('RDC', 'Warehouse RDC'),
                          ('DO', 'Dropship DO')],
                                          string='EDI Packaging Type')
    edi_vendor_number = fields.Char('Vendor # from Customer')
    ship_to_name = fields.Char('Ship to name')
    ship_to_address_1 = fields.Char('Ship to address 1')
    ship_to_address_2 = fields.Char('Ship to address 2')
    ship_to_city = fields.Char('Ship to city')
    ship_to_state = fields.Char('Ship to state')
    ship_to_zip = fields.Char('Ship to zip')
    ship_to_country = fields.Char('Ship to country')
    ship_from_name = fields.Char('Ship from name')
    ship_from_warehouse = fields.Many2one('stock.warehouse', compute='get_ship_from_warehouse', store=False)
    ship_from = fields.Many2one('res.partner', compute='_compute_ship_from_address')
    ship_from_address_1 = fields.Char('Ship from address 1', compute='_compute_ship_from_address'
                                      )
    ship_from_address_2 = fields.Char('Ship from address 2', compute='_compute_ship_from_address'
                                      )
    ship_from_city = fields.Char('Ship from city', compute='_compute_ship_from_address')
    ship_from_state = fields.Char('Ship from state', compute='_compute_ship_from_address'
                                  )
    ship_from_zip = fields.Char('Ship from zip', compute='_compute_ship_from_address')
    ship_from_country = fields.Char('Ship from country', compute='_compute_ship_from_address'
                                    )
    x_studio_edi_carton_count = fields.Integer('Package Count', default=1, compute="_compute_package_count",
                                               store=False)
    asn_created = fields.Boolean('Notification Sent?')

    def _compute_ship_from_address(self):
        for rec in self:
            rec.ship_from = rec.ship_from_warehouse.partner_id
            rec.ship_from_address_1 = rec.ship_from.street
            rec.ship_from_address_2 = rec.ship_from.street2
            rec.ship_from_city = rec.ship_from.city
            rec.ship_from_state = rec.ship_from.state_id.name
            rec.ship_from_zip = rec.ship_from.zip
            rec.ship_from_country = rec.ship_from.country_id.name

    @api.depends('location_id')
    def get_ship_from_warehouse(self):
        for pick in self:
            pick.ship_from_warehouse = pick.location_id.get_warehouse()

    def release_available_to_promise(self):
        res = super(Picking, self).release_available_to_promise()
        sale = self.env['sale.order'].search([('name', '=', self.sale_id.name)], limit=1)
        pickings = sale.picking_ids
        if pickings:
            pickings.filtered(lambda pick: pick.id != self.id).write({'x_edi_accounting_id': sale.x_edi_accounting_id,
                                                                      'x_studio_edi_store_number': sale.x_edi_store_number,
                                                                      'x_studio_edi_packaging_type': self.x_studio_edi_packaging_type
                                                                      })
            op_pick = pickings.filtered(lambda pick: pick.picking_type_id.code == 'outgoing')
            # pickings.write({
            #     'ship_from_warehouse': op_pick.location_id.get_warehouse().id
            # })
        return res

    @api.depends('package_ids', 'x_studio_edi_packaging_type')
    def _compute_package_count(self):
        for record in self:
            # record.x_studio_edi_carton_count = len(record.package_ids) if len(record.package_ids) > 1 else 1
            record.x_studio_edi_carton_count = len(record.move_line_ids_without_package) if len(
                record.move_line_ids_without_package) > 1 else 1

    @api.model
    def create(self, vals):
        picking = super(Picking, self).create(vals)

        picking.x_edi_accounting_id = picking.sale_id.x_edi_accounting_id or picking.backorder_id.x_edi_accounting_id
        picking.ship_to_name = picking.partner_id.name
        picking.ship_to_address_1 = picking.partner_id.street
        picking.ship_to_address_2 = picking.partner_id.street2
        picking.ship_to_city = picking.partner_id.city
        picking.ship_to_state = picking.partner_id.state_id.name
        picking.ship_to_country = picking.partner_id.country_id.name
        picking.ship_to_zip = picking.partner_id.zip
        picking.ship_from_name = picking.company_id.name
        return picking

    def create_asn(self, sftp):
        """
        Will upload 856 type of .csv file on sftp server.

        @param sftp: sftp instance.
        @return: True of False.
        """
        order = self.sale_id
        # BEGINS CREATE ASN
        sftp_conf = self.env['setu.sftp'].search(
            [('company_id', '=', self.company_id.id), ('instance_active', '=', True)])
        ftpdpath = sftp_conf['ftp_shipack_dpath']
        file_name = '/tmp/' + str(DOC_PREFIX_ASN) + '_' + \
                    str(order.name) + 'OUT' + str(self.id) + '_' + str(order.partner_id.name) \
                    + '.csv'  # mayBe x_edi_reference is better
        with open(file_name, 'w') as file_pointer:
            cvs_rows = []
            writer = csv.DictWriter(file_pointer, fieldnames=ASN_FIELDS)
            writer.writeheader()
            line_count = 0

            for row in self.edi_log_ref.edi_856_log_lines:
                line_count += 1
                cvs_rows.append({
                    'TRANSACTION TYPE': DOC_PREFIX_ASN,
                    'ACCOUNTING ID': row.accounting_id,
                    'SHIPMENT ID': row.shipment_id,
                    'SCAC': row.x_studio_scac,
                    'CARRIER PRO NUMBER': row.carrier_tracking_ref,
                    'BILL OF LADING': row.bill_of_landing,
                    'SCHEDULED DELIVERY': 'null',
                    'SHIP DATE': str(row.date_done) or False,
                    'SHIP TO NAME': row.ship_to_name,
                    'SHIP TO ADDRESS - LINE ONE':
                        row.ship_to_address_1 or 'null',
                    'SHIP TO ADDRESS - LINE TWO':
                        row.ship_to_address_2 or 'null',
                    'SHIP TO CITY': row.ship_to_city or 'null',
                    'SHIP TO STATE': row.ship_to_state or 'null',
                    'SHIP TO ZIP': row.ship_to_zip or 'null',
                    'SHIP TO COUNTRY': row.ship_to_country or 'null',
                    'SHIP TO ADDRESS CODE': 'null',
                    'SHIP VIA': row.ship_via or '',
                    'SHIP TO TYPE': row.x_edi_ship_to_type,
                    'PACKAGING TYPE': row.x_studio_edi_packaging_type,
                    'GROSS WEIGHT': row.weight,
                    'GROSS WEIGHT UOM': row.weight_uom_name,
                    'NUMBER OF CARTONS SHIPPED': row.x_studio_edi_carton_count,
                    'CARRIER TRAILER NUMBER': 'null',
                    'TRAILER INITIAL': 'null',

                    'SHIP FROM NAME': row.ship_from_company_id.name,
                    'SHIP FROM ADDRESS - LINE ONE': row.ship_from_street or 'null',
                    'SHIP FROM ADDRESS - LINE TWO': row.ship_from_street2 or 'null',
                    'SHIP FROM CITY': row.ship_from_city or 'null',
                    'SHIP FROM STATE': row.ship_from_state or 'null',
                    'SHIP FROM ZIP': row.ship_from_zip or 'null',
                    'SHIP FROM COUNTRY': row.ship_from_country or 'null',
                    'SHIP FROM ADDRESS CODE': 'null',
                    'VENDOR NUMBER': order.partner_id.edi_vendor_number,
                    'DC CODE': 'null',
                    'TRANSPORTATION METHOD': 'null',
                    'PRODUCT GROUP': 'null',
                    'STATUS': 'Complete Shipment ' if row.status == 'complete' else 'Partial Shipment',
                    'TIME SHIPPED': 'null',
                    'PO NUMBER': row.po_number,
                    'PO DATE': row.po_date,
                    'INVOICE NUMBER': 'null',
                    'ORDER WEIGHT': row.weight,
                    'STORE NAME': row.store_name,
                    'STORE NUMBER': row.store_number,
                    'MARK FOR CODE': 'null',
                    'DEPARTMENT NUMBER': 'null',
                    'ORDER LADING QUANTITY': row.x_studio_edi_carton_count or 'null',
                    'PACKAGING TYPE': row.x_studio_edi_packaging_type,
                    'UCC-128': row.ucc_128 or line_count,
                    'PACK SIZE': 'null',
                    'INNER PACK PER OUTER PACK': 'null',
                    'PACK HEIGHT': 'null',
                    'PACK LENGTH': 'null',
                    'PACK WIDTH': 'null',
                    'PACK WEIGHT': 'null',
                    'QTY OF UPCS WITHIN PACK': row.upc_within_pack,
                    'UOM OF UPCS': row.uom_of_upc,
                    'LINE NUMBER': line_count,
                    'VENDOR PART NUMBER': row.vendor_number or '',
                    'BUYER PART NUMBER': row.buyer_part_number,
                    'UPC NUMBER': row.upc,
                    'ITEM DESCRIPTION': row.description_sale,
                    'QUANTITY SHIPPED': row.quantity_done or 0.0,
                    'UOM': row.uom,
                    'QUANTITY ORDERED': row.product_uom_quantity or 0.0,
                    'UNIT PRICE': row.unit_price,
                    'PACK SIZE': 'null',
                    'PACK UOM': 'null',
                    'INNER PACKS PER OUTER PACK': 'null'
                })
            writer.writerows(cvs_rows)
            file_pointer.close()
        if sftp:
            sftp.cwd(ftpdpath)
            partner_name = order.partner_id.name
            partner_name = re.sub('[^a-zA-Z0-9 \n\.]', '', partner_name)
            sftp.put(file_name,
                     ftpdpath + '/' + str(DOC_PREFIX_ASN) + '_' + str(order.name) + '_' + str(
                         self.name.replace('/', '_')) + '_' + \
                     str(partner_name) + '.csv')
            return True
        return False

    def create_asg_log(self, moves, po_number):
        """
        It will create shipping notification log.

        @param moves: moves are move_ids_withot_package of picking.
        @param process: 'auto' created log or 'manual' created log.
        @param po_number: purchase order number from 850.
        @return: log_id:
        """
        batch_transfer_header_vals = self.env.context.get('batch_transfer_header_vals', {})
        log_id = self.env['setu.edi.log'].create({
            'po_number': po_number,
            'type': 'export',
            'document_type': '856'
        })
        for row in moves:
            log_line = self.with_context(
                batch_transfer_header_vals=batch_transfer_header_vals)._create_856_log_line_by_package(row)
            log_id.write({
                'edi_856_log_lines': [(4, log_line.id)]
            })
        if batch_transfer_header_vals:
            log_line_status_vals = log_id.edi_856_log_lines and log_id.edi_856_log_lines.mapped('status')
            if log_line_status_vals and 'partial' in log_line_status_vals:
                for line in log_id.edi_856_log_lines:
                    line.status = 'partial'
        moves.picking_id.edi_log_ref = log_id
        return log_id

    def _prepare_log_line_vals(self, row):
        ship_to_type = False
        has_bach_ship_to_type = self.env.context.get('combine_del_ship_to_type', False)
        if has_bach_ship_to_type:
            ship_to_type = has_bach_ship_to_type

        user_tz = pytz.timezone(self.env.user.tz or 'utc')
        asn_log_vals = {
            'upc': row.product_id.barcode or row.move_id.sale_line_id.upc_num,
            'picking_id': row.picking_id.id,
            'accounting_id': row.picking_id.x_edi_accounting_id,
            'po_number': row.picking_id.sale_id.client_order_ref,
            'po_date': str(row.picking_id.sale_id.date_order.astimezone(
                user_tz).date()) if row.picking_id and row.picking_id.sale_id else False,
            'ship_from_company_id': row.picking_id.company_id.id,
            'ship_to_name': row.picking_id.partner_id.x_edi_store_number,
            'ship_to_address_1': row.picking_id.ship_to_address_1,
            'ship_to_address_2': row.picking_id.ship_to_address_2,
            'ship_to_city': row.picking_id.ship_to_city,
            'ship_to_state': row.picking_id.ship_to_state,
            'ship_to_zip': row.picking_id.ship_to_zip,
            'ship_to_country': row.picking_id.ship_to_country,
            'carrier_tracking_ref': row.picking_id.carrier_tracking_ref,
            'origin_sale_order': row.picking_id.sale_id.id,
            'bill_of_landing': row.picking_id.sale_id.name,
            'date_done': str(row.picking_id.date_done.astimezone(user_tz).date()),
            'store_name': row.picking_id.partner_id.name,
            'shipment_id': row.picking_id.name,
            'x_studio_scac': row.picking_id.x_scac_kuebix or (
                    row.picking_id.carrier_id and row.picking_id.carrier_id.x_scac) or '',
            'carrier_id': False,
            'ship_via': row.picking_id.shipping_service if row.picking_id.carrier_id and row.picking_id.carrier_id.delivery_type == 'kuebix' else row.picking_id.carrier_id.name if row.picking_id.carrier_id else '',
            'x_studio_edi_packaging_type': row.picking_id.x_studio_edi_packaging_type,
            'weight': row.picking_id.weight,
            'weight_uom_name': row.picking_id.weight_uom_name,
            'x_studio_edi_carton_count': row.picking_id.x_studio_edi_carton_count,
            'vendor_number': row.product_id.default_code,
            'uom': row.product_uom_id.name,

            'product_id': row.product_id.default_code,
            'description_sale': row.product_id.name,

            'ship_from_warehouse': row.picking_id.ship_from_warehouse.id,

            'unit_price': row.move_id.sale_line_id.price_unit,
            'buyer_part_number': row.move_id.sale_line_id.po_log_line_id.buyers_part_num,
            'x_edi_ship_to_type': ship_to_type or row.picking_id.partner_id.x_edi_ship_to_type,

            'ucc_128': row.move_id.sale_line_id.x_edi_po_line_number
        }
        return asn_log_vals

    def _create_856_log_line_by_package(self, row):
        """
        Will create log lines for shipping notification type of log.

        @param row: row is line from move_ids_without_package of picking.
        @param process: 'auto' or 'manual' process. Used to calculate real product_uom_qty before picking was validated.
        @return: asn_log_vals: log_line_values
        """
        product_uom_qty = row.initial_product_uom_qty
        if row.initial_product_uom_qty == row.qty_done:
            status = 'complete'
        else:
            status = 'partial'

        package = row.result_package_id.quant_ids.filtered(lambda q: q.product_id == row.product_id)
        qty_upc_within_pack = package[0].quantity if package else False
        uom_of_upc = package[0].product_uom_id.name if package else False

        asn_vals = self._prepare_log_line_vals(row)
        asn_vals.update({
            'status': status,
            'product_uom_quantity': product_uom_qty,
            'quantity_done': row.qty_done,
            'upc_within_pack':
                qty_upc_within_pack or 'null',
            'uom_of_upc': uom_of_upc or 'null'
        })
        batch_transfer_header_vals = self.env.context.get('batch_transfer_header_vals', {})
        single_picking_sending_scac = self.env.context.get('scac_kuebix_combined', {})
        batch_ship_via = self.env.context.get('batch_ship_via', {})
        if batch_ship_via:
            asn_vals['ship_via'] = batch_ship_via
        if single_picking_sending_scac:
            asn_vals['x_studio_scac'] = single_picking_sending_scac
        if batch_transfer_header_vals:
            delivery_address = batch_transfer_header_vals['delivery_address']
            asn_vals.update({
                'weight': batch_transfer_header_vals['gross_weight'],
                'shipment_id': batch_transfer_header_vals['shipment_id'],
                'bill_of_landing': batch_transfer_header_vals['bill_of_landing'],
                'x_studio_edi_carton_count': batch_transfer_header_vals['package_count'],
                'ship_to_name': delivery_address.x_edi_store_number,
                'ship_to_address_1': delivery_address.street,
                'ship_to_address_2': delivery_address.street2,
                'ship_to_city': delivery_address.city,
                'ship_to_state': delivery_address.state_id and delivery_address.state_id.name or '',
                'ship_to_zip': delivery_address.zip,
                'ship_to_country': delivery_address.country_id and delivery_address.country_id.name or '',
                'x_edi_ship_to_type': batch_transfer_header_vals['x_edi_ship_to_type']
            })
            if batch_transfer_header_vals['scac']:
                asn_vals['x_studio_scac'] = batch_transfer_header_vals['scac']
            if batch_transfer_header_vals['batch_ship_via']:
                asn_vals['ship_via'] = batch_transfer_header_vals['batch_ship_via']

        log_line = self.env['setu.shipack.export.log.line'].create(asn_vals)
        return log_line

    def action_done(self):
        """
        This function is used to create ASNPn(856) file represent picking and
         its move line data. It will create .csv file into grab folder location
        :return:
        """

        for move in self.move_line_ids_without_package:
            move.initial_product_uom_qty = move.product_uom_qty

        res = super(Picking, self).action_done()
        for rec in self:
            # if res and rec.partner_id and rec.sale_id and rec.sale_id.partner_id.x_edi_flag and rec.partner_id.edi_856 and rec.partner_id.x_edi_flag and rec.picking_type_id.code == 'outgoing' and not rec.asn_created:
            if res and rec.partner_id and rec.sale_id and rec.sale_id.partner_invoice_id.x_edi_flag and rec.partner_id.edi_856 and rec.partner_id.x_edi_flag and rec.picking_type_id.code == 'outgoing' and not rec.asn_created:
                rec.create_asn_log_and_asn_export()
        return res

    def create_asn_log_and_asn_export(self):
        """
        Main method to create log and export both of 856 document.
        @param moves_value_dict: moves quantity values before picking is validated.
        @return: log_ids: will return log_ids of asn.
        """
        log_ids = self.env['setu.edi.log']
        batch_transfer_header_vals = self.env.context.get('batch_transfer_header_vals', {})
        for pick in self:
            moves = False
            picks = False
            bill_ship_picks_dict = self.env.context.get('bill_ship_picks_dict')

            if type(bill_ship_picks_dict) != dict:
                moves = pick.move_line_ids_without_package
                picks = pick
                process = 'auto'
            else:
                delivery_partner = pick.partner_id
                if batch_transfer_header_vals:
                    delivery_partner = batch_transfer_header_vals['delivery_address']
                bill_ship = str(pick.sale_id.partner_id.id) + ',' + str(delivery_partner.id)
                if bill_ship in bill_ship_picks_dict.keys():
                    common_address_picks = bill_ship_picks_dict[bill_ship]
                    moves = common_address_picks.move_line_ids_without_package
                    picks = bill_ship_picks_dict[bill_ship]
                    del bill_ship_picks_dict[bill_ship]
                process = 'manual'

            if moves:
                po_number = False
                po_number_list = list(
                    map(lambda sale: sale.x_edi_reference if sale.x_edi_reference else False, moves.picking_id.sale_id))
                po_number_list = [x for x in po_number_list if x]
                if po_number_list:
                    po_number = ", ".join(po_number_list)

                sftp_conf = self.env['setu.sftp'].search(
                    [('company_id', '=', pick.company_id.id), ('instance_active', '=', True)])
                sftp, status = sftp_conf.test_connection()
                if sftp:

                    log_id = pick.with_context(batch_transfer_header_vals=batch_transfer_header_vals).create_asg_log(
                        moves, po_number)

                    log_ids |= log_id
                    ack = pick.create_asn(sftp)
                    if ack:
                        log_id.status = 'success'
                        if picks:
                            log_id.picking_ids = picks
                            picks.asn_created = True
                    else:
                        log_id.status = 'fail'
                else:
                    log_ids = self.env['setu.edi.log'].create({
                        'po_number': po_number,
                        'type': 'export',
                        'document_type': '856',
                        'status': 'fail',
                        'exception': status,
                        'picking_ids': picks.ids
                    })
                    picks.edi_log_ref = log_ids

        return log_ids

    def check_and_validate_pickings(self, pickings):
        base_sale_partner = False
        base_source_location = False
        wrong_type_pickings = []
        picking_ids = self.browse(pickings)
        done_cancel_pickings = picking_ids.filtered(lambda p: p.state in ('done', 'cancel'))
        # batch_allocated = picking_ids.filtered(lambda pick: pick.batch_id)
        # if batch_allocated:
        #     transfers = ",".join(batch_allocated.mapped('name'))
        #     return False, f"The Transfer {transfers} cannot be added, the Transfer must not be in any batch."
        if done_cancel_pickings:
            transfers = ",".join(done_cancel_pickings.mapped('name'))
            return False, f"The Transfer {transfers} cannot be added, the Transfer or Batch must not be in Done or Cancel state."
        type_wrong_picks = picking_ids.filtered(lambda p: p.picking_type_id.code != 'outgoing')
        if type_wrong_picks:
            transfers = ",".join(type_wrong_picks.mapped('name'))
            return False, f"The Transfer {transfers} cannot be added, the Transfer must be a Delivery Order"
        else:
            for p in picking_ids:
                if not base_source_location:
                    base_source_location = p.location_id
                if base_source_location != p.location_id:
                    return False, 'The transfers cannot be combined, all transfers must be delivered from a same location.'
                if not base_sale_partner:
                    base_sale_partner = p.sale_id and p.sale_id.partner_id
                if not base_sale_partner:
                    return False, 'No sale order attached with one of the transfers.'
                if base_sale_partner != p.sale_id.partner_id:
                    return False, 'You can only combine Delivery Orders for the same Customer, please select Delivery  Orders with the same Customer on the Sales Order'
        return True, 'Pass'

    def combine_pickings_and_make_batch(self):
        active_ids = self._context.get('active_ids', [])
        if not active_ids:
            raise UserError("Please select Delivery Transfers to do this operation.")
        pickings = active_ids  # self.env.context['active_ids']
        message = self.env['batch.selector'].create({
            'message_id': 'Batch created successfully.',
            'batch_id': False
        })
        res, notification = self.check_and_validate_pickings(pickings)
        if res:
            batch = self.env['stock.picking.batch'].with_context(combined_delivery_orders=True).create({
                'picking_ids': pickings
            })
            batch.is_combined_tranfers_batch = True
            batch._compute_sale_partner()
            message.batch_id = batch
            message.batch_created = True
        else:
            message.message_id = notification
        context = self._context.copy() or {}
        return {
            'name': _('Notification'),
            'view_type': 'form',
            'view_mode': 'form',
            # 'view_id': self.env.ref('captivea_edi.batch_selector_form_view').id,
            'res_model': 'batch.selector',
            'views': [(self.env.ref('captivea_edi.batch_selector_form_view').id, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': message.id,
            'context': context
        }

    def add_picking_to_batch(self):
        context = self._context.copy() or {}
        active_ids = context.get('active_ids', [])
        if not active_ids:
            raise UserError("Please select Delivery Transfers to do this operation.")
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'batch.selector',
            # 'view_id': self.env.ref('captivea_edi.batch_selector_form_view').id,
            'views': [(self.env.ref('captivea_edi.batch_selector_form_view').id, 'form')],
            'view_mode': 'form',
            'name': _('Select Batch'),
            'target': 'new',
            'domain': [('state', 'not in', ('done', 'cancel'))],
            'context': context
        }


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    initial_product_uom_qty = fields.Float()
    combine_batch_id = fields.Many2one('stock.picking.batch')


class BatchSelector(models.TransientModel):
    _name = 'batch.selector'
    _description = 'Batch Selector'

    batch_id = fields.Many2one('stock.picking.batch')
    message_id = fields.Char()
    batch_created = fields.Boolean(default=False)

    def open_batch(self):
        context = self._context.copy() or {}
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.batch',
            'view_id': self.env.ref('captivea_edi.captivea_stock_picking_batch_form_view').id,
            # 'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'form',
            'name': _('Combined Delivery Order'),
            'res_id': self.batch_id.id,
            'context': context
        }

    def add_to_batch(self):
        context = self._context.copy() or {}
        active_ids = context.get('active_ids', [])
        if not active_ids:
            raise UserError("Please select Delivery Transfers to do this operation.")
        batch = self.batch_id
        batch_pick = False
        batch_pickings = batch.picking_ids
        if batch_pickings:
            batch_pick = batch_pickings[0]
        pickings_ids = active_ids  # self.env.context['active_ids']

        if batch_pick:
            pickings = self.env['stock.picking'].browse(pickings_ids) | batch_pick
            res, notification = self.env['stock.picking'].check_and_validate_pickings(pickings.ids)
            if res:
                pickings_ids = list(map(lambda pick: (4, pick), pickings_ids))
                batch.with_context(combined_delivery_orders=True).write({
                    'picking_ids': pickings_ids
                })
                self.message_id = 'Delivery orders added to the batch.'
                self.batch_created = True
            else:
                self.message_id = notification
                # self.batch_id = False
        else:
            pickings_ids = list(map(lambda pick: (4, pick), pickings_ids))
            batch.with_context(combined_delivery_orders=True).write({
                'picking_ids': pickings_ids
            })
            self.message_id = 'Delivery orders added to the batch.'
        # self.batch_id = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'batch.selector',
            'view_id': self.env.ref('captivea_edi.batch_selector_form_view').id,
            # 'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'form',
            'name': _('Select Batch'),
            'target': 'new',
            'res_id': self.id,
            'context': context
        }
