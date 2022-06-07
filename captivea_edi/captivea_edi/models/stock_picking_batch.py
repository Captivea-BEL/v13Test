import requests

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from requests.auth import HTTPBasicAuth


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    x_studio_edi_packaging_type = fields.Selection([('Pallet', 'Pallet'), ('Carton', 'Carton')],
                                                   string='EDI Packaging Type', default='Carton')

    source_loc_id = fields.Many2one('stock.location', string='Source Location',
                                    store=True)
    delivery_address = fields.Many2many('res.partner',
                                        compute='_compute_partner_ids')

    is_combined_tranfers_batch = fields.Boolean(default=False)

    @api.depends('picking_ids')
    def _compute_partner_ids(self):
        for rec in self:
            if rec.picking_ids:
                rec.delivery_address = rec.picking_ids.mapped('partner_id')
            else:
                rec.delivery_address = False

    delivery_address_id = fields.Many2one('res.partner')

    #
    # @api.depends('picking_ids')
    # def _compute_source_loc(self):
    #     for batch in self:
    #         if batch.picking_ids:
    #             batch.source_loc_id = batch.picking_ids[0].location_id
    #
    # @api.depends('picking_ids')
    # def _compute_delivery_address(self):
    #     for batch in self:
    #         if batch.picking_ids:
    #             partners = self.env['res.partner']
    #             for pick in batch.picking_ids:
    #                 partners |= pick.partner_id
    #             batch.delivery_address = partners

    edi_asn_single = fields.Boolean(default=False, string='Consolidate 856', compute='_compute_edi_asn_single',
                                    store=True)

    @api.depends('sale_partner', 'sale_partner.edi_asn_single')
    def _compute_edi_asn_single(self):
        for rec in self:
            if rec.picking_ids:
                rec.edi_asn_single = rec.sale_partner and rec.sale_partner.edi_asn_single or rec.picking_ids[
                    0].sale_id.partner_id.edi_asn_single

    x_edi_accounting_id = fields.Char('Trading Partner ID', related='partner_id.x_edi_accounting_id', copy=False)

    x_edi_ship_to_type = fields.Selection([('DC', 'Warehouse Number'),
                          ('SN', 'Store Number'),
                          ('TPSO', 'Dropship TPSO'),
                          ('RDC', 'Warehouse RDC'),
                          ('DO', 'Dropship DO')],
                                          related='delivery_address_id.x_edi_ship_to_type', string='Ship To Type')
    edi_vendor_number = fields.Char(related='partner_id.edi_vendor_number', string='Vendor # from Customer')
    ship_to_name = fields.Char('Ship to name')
    ship_to_address_1 = fields.Char('Ship to address 1')
    ship_to_address_2 = fields.Char('Ship to address 2')
    ship_to_city = fields.Char('Ship to city')
    ship_to_state = fields.Char('Ship to state')
    ship_to_zip = fields.Char('Ship to zip')
    ship_to_country = fields.Char('Ship to country')
    ship_from_name = fields.Char(related='company_id.name', string='Ship From Name')

    ship_from = fields.Many2one(related='warehouse_id.partner_id')
    ship_from_address_1 = fields.Char('Ship from address 1', related='ship_from.street')
    ship_from_address_2 = fields.Char('Ship from address 2', related='ship_from.street2')
    ship_from_city = fields.Char('Ship from city', related='ship_from.city')
    ship_from_state = fields.Char('Ship from state', related='ship_from.state_id.name')
    ship_from_zip = fields.Char('Ship from zip', related='ship_from.zip')
    ship_from_country = fields.Char('Ship from country', related='ship_from.country_id.name')
    x_studio_edi_carton_count = fields.Integer('Package Count', compute='_compute_carton_count')

    @api.depends('picking_ids', 'picking_ids.x_studio_edi_carton_count')
    def _compute_carton_count(self):
        for rec in self:
            if rec.picking_ids:
                rec.x_studio_edi_carton_count = sum(rec.picking_ids.mapped('x_studio_edi_carton_count'))
            else:
                rec.x_studio_edi_carton_count = 0

    asn_created = fields.Boolean('Notification Sent?', compute='_compute_asn_sent')

    store_number = fields.Char(related='delivery_address_id.x_edi_store_number', copy=False)

    warehouse_id = fields.Many2one('stock.warehouse')
    shipping_type_id = fields.Many2one('stock.picking.type')
    partner_id = fields.Many2one('res.partner', string='Sale Order Partner')
    move_line_ids = fields.One2many('stock.move.line', 'combine_batch_id', compute='_compute_move_lines', store=True)
    sale_partner = fields.Many2one('res.partner', compute='_compute_sale_partner', store=True)
    shipping_type_select = fields.Selection([('kuebix', 'Kuebix'), ('manual', 'Manual')], string="Select Shipping Type",
                                            required=True, default='kuebix')

    @api.depends('picking_ids')
    def _compute_sale_partner(self):
        for rec in self:
            rec.sale_partner = rec.picking_ids and rec.picking_ids[0].sale_id.partner_id or False

    def _compute_asn_sent(self):
        for batch in self:
            if batch.picking_ids and any(batch.picking_ids.mapped('asn_created')):
                batch.asn_created = True
            else:
                batch.asn_created = False

    @api.depends('picking_ids', 'picking_ids.move_line_ids_without_package')
    def _compute_move_lines(self):
        for batch in self:
            if batch.picking_ids:
                batch.move_line_ids = batch.picking_ids.move_line_ids_without_package
            else:
                batch.move_line_ids = False

    # @api.depends('picking_ids')
    # def _compute_shipping_type(self):
    #     for batch in self:
    #         if batch.picking_ids:
    #             batch.shipping_type_id = batch.picking_ids[0].picking_type_id
    #
    # @api.depends('x_studio_edi_packaging_type')
    # def _compute_package_count(self):
    #     for batch in self:
    #         if batch.picking_ids:
    #             batch.picking_ids.x_studio_edi_packaging_type = batch.x_studio_edi_packaging_type
    #             batch.x_studio_edi_carton_count = sum([pick.x_studio_edi_carton_count for pick in batch.picking_ids])
    #
    # @api.depends('source_loc_id')
    # def _compute_warehouse_id(self):
    #     for batch in self:
    #         if batch.source_loc_id:
    #             batch.warehouse_id = batch.source_loc_id.get_warehouse()

    def create_batch_kuebix_shipment(self):
        for rec in self:
            if rec.delivery_address_id:
                delivery_address_partner = rec.delivery_address_id
            # else:
            #     raise ValidationError(_("Cannot Create Kuebix Shipment for more than one delivery address!"))
            if not rec.source_loc_id.company_id.username or \
                    not rec.source_loc_id.company_id.password \
                    or not rec.source_loc_id.company_id.client_id:
                raise MissingError(_(
                    'Something is missing Username, Password or Client ID'))
            elif not delivery_address_partner.country_id or \
                    not delivery_address_partner.zip:
                raise MissingError(_('Please enter proper delivery address '
                                     'details.'))
            elif not rec.source_loc_id.company_id.partner_id.country_id or \
                    not rec.source_loc_id.company_id.partner_id.zip:
                raise MissingError(
                    _('Please enter proper warehouse address details.'))
            elif rec.kuebix_shipment_processed == True:
                raise Warning(_("Shipment is Already processed for this order!"))
            else:
                try:
                    url = "https://shipment.kuebix.com/api/shipments"
                    auth_str = HTTPBasicAuth(
                        rec.source_loc_id.company_id.username,
                        rec.source_loc_id.company_id.password)
                    headers = {
                        'Content-Type': "application/json",
                        'cache-control': "no-cache",
                    }
                    if rec.picking_ids:
                        lineItems = []
                        handlingUnits = []
                        packages = []
                        ship_pack_dict = {}
                        ship_pkgs = self.env['shipping.packaging']
                        count = 0
                        for picking in rec.picking_ids.filtered(lambda p: p.kuebix_processed == False):
                            count += 1
                            shipping_packages = picking.move_line_ids_without_package.mapped('shipping_package')
                            ship_pkgs |= shipping_packages
                            if shipping_packages:
                                # LTL API call item details
                                for ship_pack in shipping_packages:
                                    mv_line_list = []
                                    for mv_line in picking.move_line_ids_without_package.filtered(
                                            lambda mvl: mvl.shipping_package.id == ship_pack.id):
                                        mv_line_list.append(mv_line)
                                    if ship_pack_dict and ship_pack in ship_pack_dict.keys():
                                        for ml in mv_line_list:
                                            ship_pack_dict[ship_pack].append(ml)
                                    else:
                                        ship_pack_dict.update({ship_pack: mv_line_list})
                        # for picking in rec.picking_ids.filtered(lambda p: p.kuebix_processed == False):
                        #     shipping_packages = picking.move_line_ids_without_package.mapped('shipping_package')
                        #     print ("shipping_packages --->>", shipping_packages)
                        if ship_pkgs:
                            # LTL API call item details
                            # ship_pack_dict = {}
                            # for ship_pack in shipping_packages:
                            #     mv_line_list = []
                            #     for mv_line in picking.move_line_ids_without_package.filtered(lambda mvl: mvl.shipping_package.id == ship_pack.id):
                            #         mv_line_list.append(mv_line)
                            #     ship_pack_dict.update({ship_pack:mv_line_list})
                            # print ("picking --->>", picking)
                            # print ("ship_pack_dict --->>", ship_pack_dict)
                            # sljdvnsjkfvfd
                            for k, v in ship_pack_dict.items():
                                # LTL API call item details
                                lineItems.append({
                                    "packageReference": k.name,
                                    "packageType": "Box(es)",
                                    "description": "Magnets",
                                    "weight": 9999,
                                    "freightClass": "77.5",
                                    "poNumber": rec.name  # order.client_order_ref
                                })
                                handlingUnits.append({
                                    "reference": k.name,
                                    "huType": "Pallet(s)" if k.is_pallet == True else "Box(es)",
                                    "quantity": 1,
                                    "freightClass": "77.5",
                                    "description": "Magnets",
                                    "weight": 9999,
                                    "length": 48,
                                    "width": 40,
                                })
                                packages.append({
                                    "quantity": len(v),
                                    "weight": 9999,
                                    "length": 48,
                                    "width": 40,
                                    "reference": k.name,
                                    "handlingUnitReference": k.name,
                                    "freightClass": "77.5",
                                    "description": "Magnets",
                                })
                        elif not ship_pkgs:
                            for picking in rec.picking_ids.filtered(lambda p: p.kuebix_processed == False):
                                for move_line in picking.move_line_ids_without_package:
                                    # if (move_line.shipping_package or move_line.result_package_id) and self.shipment_type == 'parcel':
                                    # Parcel API call item details
                                    lineItems.append({
                                        "packageReference": move_line.result_package_id.name,
                                        "packageType": "Box(es)",
                                        "description": "Magnets",
                                        "weight": 9999,
                                        "freightClass": "77.5",
                                        "poNumber": rec.name  # order.client_order_ref
                                    })
                                    handlingUnits.append({
                                        "reference": move_line.result_package_id.name,
                                        "huType": "Box(es)",
                                        "quantity": 1,
                                        "freightClass": "77.5",
                                        "weight": 9999,
                                        "length": 48,
                                        "width": 40,
                                    })
                                    packages.append({
                                        "quantity": 1,
                                        "weight": 9999,
                                        "length": 48,
                                        "width": 40,
                                        "freightClass": "77.5",
                                        "reference": move_line.result_package_id.name,
                                        "handlingUnitReference": move_line.result_package_id.name,
                                    })
                        payload = {
                            "origin": {
                                "companyName":
                                    rec.source_loc_id.company_id.partner_id.name,
                                "country":
                                    rec.source_loc_id.company_id.partner_id.country_id.name,
                                "stateProvince":
                                    rec.source_loc_id.company_id.partner_id.state_id.code,
                                "city": rec.source_loc_id.company_id.partner_id.city,
                                "streetAddress":
                                    rec.source_loc_id.company_id.partner_id.street + (
                                            rec.source_loc_id.company_id.partner_id.street2 or ''),
                                "postalCode": rec.source_loc_id.company_id.partner_id.zip,
                                "contact": {
                                    "name": rec.source_loc_id.company_id.partner_id.name,
                                    "email": rec.source_loc_id.company_id.partner_id.email or '',
                                },
                                "notes": "Example note"
                            },
                            "destination": {
                                "companyName": delivery_address_partner.name,
                                "country":
                                    delivery_address_partner.country_id.name,
                                "stateProvince":
                                    delivery_address_partner.state_id.code,
                                "city": delivery_address_partner.city,
                                "streetAddress": delivery_address_partner.street + (
                                        delivery_address_partner.street2 or ''),
                                "postalCode": delivery_address_partner.zip,
                                "contact": {
                                    "name": delivery_address_partner.name,
                                    "email": delivery_address_partner.email or '',
                                }
                            },
                            "billTo": {
                                "companyName": rec.source_loc_id.company_id.partner_id.name,
                                "country":
                                    rec.source_loc_id.company_id.partner_id.country_id.name,
                                "stateProvince":
                                    rec.source_loc_id.company_id.partner_id.state_id.code,
                                "city": rec.source_loc_id.company_id.partner_id.city,
                                "streetAddress": rec.source_loc_id.company_id.partner_id.street + (
                                        rec.source_loc_id.company_id.partner_id.street2 or ''),
                                "postalCode": rec.source_loc_id.company_id.partner_id.zip,
                                "contact": {
                                    "name": rec.source_loc_id.company_id.partner_id.name,
                                    "email": rec.source_loc_id.company_id.partner_id.email or '',
                                }
                            },
                            "client": {
                                "id": rec.source_loc_id.company_id.client_id,
                            },
                            "lineItems": lineItems,
                            "handlingUnits": handlingUnits,
                            "packages": packages,
                            "weightUnit": "LB",
                            "lengthUnit": "IN",
                            "shipmentType": 'LTL',
                            # dict(self._fields['shipment_type'].selection).get(self.shipment_type) or '',
                            "shipmentMode": "Dry Van",
                            "paymentType": 'Outbound Prepaid',
                            # dict(order._fields['paymenttype'].selection).get(order.paymenttype) or '',
                            "bolNumber": rec.name,
                            # "poNumbers": order.client_order_ref,
                            "soNumbers": rec.name,
                        }
                        response = requests.post(url, headers=headers,
                                                 auth=auth_str, json=payload)
                        if response.status_code == 400:
                            raise Warning(
                                _("Incorrect Request: incorrect information on the Transfer, please correct the data and validate the Transfer!"))
                        if response.status_code == 401:
                            raise Warning(
                                _("Incorrect Kuebix credentials: please contact an Administrator to change the Kuebix credentials!"))
                        if response.status_code == 500:
                            raise Warning(
                                _("Internal Kuebix Server Error. Please contact the Kuebix sales representative!"))
                        result = response.json()
                        for pick in rec.picking_ids:
                            pick.shipment_id = result['shipmentId']
                            pick.shipment_name = result['shipmentName']
                            pick.kuebix_processed = True
                        rec.kuebix_shipment_processed = True
                        rec.shipment_id = result['shipmentId']
                        rec.shipment_name = result['shipmentName']
                except Exception as e:
                    raise UserError(_('%s') % str(e))

    def delete_batch_kuebix_shipment(self):
        for rec in self:
            if rec.picking_ids:
                for picking in rec.picking_ids.filtered(lambda p: p.kuebix_processed == True):
                    del_shipment = picking.delete_kuebix_shipment()
                if rec.picking_ids.filtered(lambda p: p.kuebix_processed == False):
                    rec.kuebix_shipment_processed = False
                    rec.shipment_id = ''
                    rec.shipment_name = ''
                    rec.carrier = None
                    rec.scac = ''
                    rec.actual_shipment_cost = 0.0
                    rec.weight = 0.0
                    rec.weight_for_shipping = 0.0
                    rec.add_tracking_numbers = ''
                    rec.tracking_ref = ''

    def import_batch_shipping_detail(self):
        for rec in self:
            import_shipment = None
            if rec.picking_ids:
                for picking in rec.picking_ids.filtered(lambda p: p.kuebix_processed == True):
                    import_shipment = picking.with_context(batch_ship=True).import_shipping_detail()
                if import_shipment:
                    kuebix_carrier_id = self.env['delivery.carrier'].search([('delivery_type', '=', 'kuebix')], limit=1)
                    rec.carrier = kuebix_carrier_id.id
                    rec.shipping_service = import_shipment['bookedRateQuote']['carrierName']
                    rec.scac = import_shipment['bookedRateQuote']['scac']
                    rec.tracking_ref = import_shipment['proNumber']
                    rec.actual_shipment_cost = import_shipment['bookedRateQuote']['totalPrice']

    def action_get_batch_bol(self):
        for rec in self:
            get_bol = None
            if rec.picking_ids:
                for picking in rec.picking_ids.filtered(lambda p: p.kuebix_processed == True):
                    get_bol = picking.with_context({'batch_picking_operation': True}).action_get_bol()
                if get_bol:
                    print ("get_bol --->>", get_bol)
                    rec.weight_for_shipping = get_bol.get("weightTotal")
                    print ("rec.weight_for_shipping --->>", rec.weight_for_shipping)
                    base64_string = bytes(get_bol['base64String'], 'utf-8')
                    if base64_string:
                        pdf = self.env['ir.attachment'].create({
                            'name': 'bill_of_lading.pdf',
                            'type': 'binary',
                            'datas': base64_string,
                            'store_fname': "bill_of_lading" + ".pdf",
                            'res_model': 'stock.picking.batch',
                            'res_id': rec._origin.id,
                            'mimetype': 'application/x-pdf'
                        })

    @api.model
    def create(self, vals_list):
        res = super(StockPickingBatch, self).create(vals_list)
        if res and 'combined_delivery_orders' in self._context:
            for batch in res:
                if batch.picking_ids:
                    batch.update_combined_batch()
                if batch.source_loc_id:
                    batch.warehouse_id = batch.source_loc_id.get_warehouse()
        return res

    def write(self, vals):
        res = super(StockPickingBatch, self).write(vals)
        if res and 'from_self_batch_write' not in self._context and 'combined_delivery_orders' in self._context:
            for batch in self:
                if 'picking_ids' in vals.keys() and batch.picking_ids:
                    batch.update_combined_batch()
                if not batch.picking_ids:
                    batch.with_context(from_self_batch_write=True).write(
                        {'source_loc_id': False, 'partner_id': False, 'delivery_address': False,
                         'shipping_type_id': False, 'x_studio_edi_carton_count': 0, 'warehouse_id': False})
        if res and 'x_studio_edi_packaging_type' in vals:
            for rec in self:
                if rec.picking_ids:
                    rec.picking_ids.x_studio_edi_packaging_type = rec.x_studio_edi_packaging_type

        return res

    def update_combined_batch(self):
        for batch in self:
            values = batch.prepare_combined_batch()
            batch.with_context(from_self_batch_write=True).write(values)
            batch.picking_ids.with_context(from_self_batch_write=True).write(
                {'x_studio_edi_packaging_type': batch.x_studio_edi_packaging_type})

    def prepare_combined_batch(self):
        batch = self
        partners = batch.picking_ids.mapped('partner_id')
        delivery_address_id = self.delivery_address_id if self.delivery_address_id else partners if len(
            partners) == 1 else False
        # delivery_address_id = partners if len(partners) == 1 else (self.delivery_address_id or False)
        value = {}
        if batch.picking_ids:
            value.update({'source_loc_id': batch.picking_ids[0].location_id,
                          'delivery_address_id': delivery_address_id,
                          'partner_id': batch.picking_ids[0].sale_id and
                                        batch.picking_ids[0].sale_id.partner_id,
                          # 'delivery_address': partners,
                          'shipping_type_id': batch.picking_ids[0].picking_type_id,
                          # 'x_studio_edi_carton_count': sum(batch.picking_ids.mapped(
                          #     'x_studio_edi_carton_count')),
                          'warehouse_id': batch.source_loc_id.get_warehouse()})
        return value

    def validate_pickings(self):
        sale_partner = self.picking_ids and self.picking_ids[0] and self.picking_ids[0].sale_id.partner_id or False

        if self.edi_asn_single:
            self.picking_ids.asn_created = True
        # kuebix
        to_force_validate = self.picking_ids.move_line_ids_without_package.filtered(lambda l: l.qty_done == 0)
        for l in to_force_validate:
            l.qty_done = l.product_uom_qty
        if self.shipping_type_select == 'manual':
            pickings_done = self.picking_ids.filtered(lambda p: p.state == 'done')
            pickings_not_ready = self.picking_ids.filtered(lambda p: p.state != 'assigned')
            if pickings_not_ready:
                picking_names = ''
                for picking in pickings_not_ready:
                    if picking_names:
                        picking_names += (' ' + picking.name)
                    else:
                        picking_names += picking.name
                if not pickings_done:
                    raise ValidationError(
                        _("Delivery Order(s) %s must be in a ready state, please make sure the Pick(s) and Pack(s) have been completed") % (
                            picking_names))
            else:
                for picking in self.picking_ids:
                    picking.carrier_id = self.carrier.id
                    picking.x_scac = self.scac
                    picking.shipment_id = self.shipment_id
                    picking.shipment_name = self.shipment_name
                    picking.actual_shipment_cost = self.actual_shipment_cost
                    picking.weight = self.weight
                    picking.shipping_weight = self.weight_for_shipping
                    picking.other_tracking_numbers = self.add_tracking_numbers
                    picking.carrier_tracking_ref = self.tracking_ref
                    picking.liftgate_required = self.liftgate_required
                    picking.appointment_required = self.appointment_required
                    if self.residential_address == 'yes':
                        picking.residential = True
                    else:
                        picking.residential = False
        elif self.shipping_type_select == 'kuebix':
            pickings_done = self.picking_ids.filtered(lambda p: p.state == 'done')
            pickings_not_ready = self.picking_ids.filtered(lambda p: p.state != 'assigned')
            if pickings_not_ready:
                picking_names = ''
                for picking in pickings_not_ready:
                    if picking_names:
                        picking_names += (' ' + picking.name)
                    else:
                        picking_names += picking.name
                if not pickings_done:
                    raise ValidationError(
                        _("Delivery Order(s) %s must be in a ready state, please make sure the Pick(s) and Pack(s) have been completed") % (
                            picking_names))
        # kuebix
        ship_via = self.shipping_service if self.carrier and self.carrier.delivery_type == 'kuebix' else self.carrier.name if self.carrier else ''
        if not self.edi_asn_single:
            res = self.with_context(combine_del_ship_to_type=self.x_edi_ship_to_type, scac_kuebix_combined=self.scac,
                                    batch_ship_via=ship_via).done()
        else:
            res = self.done()
        if type(res) == bool and self.edi_asn_single:
            self.picking_ids.asn_created = False
        if type(res) == bool and res and self.edi_asn_single and sale_partner and \
                self.delivery_address_id.edi_856 and self.delivery_address_id.x_edi_flag and sale_partner.x_edi_flag:
            # if type(res) == bool and res and not self.edi_asn_single:
            bill_ship_picks_dict = {}
            pickings = self.picking_ids
            # pickings = self.picking_ids.filtered(lambda p: p.partner_id and p.partner_id.edi_856 and p.partner_id.x_edi_flag and True if not p.parent_id or p.parent_id and p.parent_id.x_edi_flag else False)
            for pick in pickings:
                bill_ship = str(pick.sale_id.partner_id.id) + ',' + str(self.delivery_address_id.id)
                if bill_ship in bill_ship_picks_dict.keys():
                    bill_ship_picks_dict[bill_ship] |= pick
                else:
                    bill_ship_picks_dict.update({
                        bill_ship: pick
                    })
            batch_transfer_header_vals = {}
            sales = pickings.mapped('sale_id')
            bill_of_landing = sales and ", ".join(sales.mapped('name'))
            shipment_id = self.name
            gross_weight = sum(pickings.mapped('weight'))
            package_count = self.x_studio_edi_carton_count
            batch_transfer_header_vals.update({
                'bill_of_landing': bill_of_landing,
                'shipment_id': shipment_id,
                'gross_weight': gross_weight,
                'package_count': package_count,
                'delivery_address': self.delivery_address_id,
                'x_edi_ship_to_type': self.x_edi_ship_to_type,
                'scac': self.scac,
                'batch_ship_via': ship_via
            })
            # if pickings:
            pickings.with_context(bill_ship_picks_dict=bill_ship_picks_dict,
                                  batch_transfer_header_vals=batch_transfer_header_vals).create_asn_log_and_asn_export()
        return res

    # @api.depends('delivery_address_id', 'delivery_address_id.liftgate_required')
    # def set_liftgate_required(self):
    #     for rec in self:
    #         rec.liftgate_required = rec.delivery_address_id.liftgate_required
    #
    # @api.depends('delivery_address_id', 'delivery_address_id.appointment_required')
    # def set_appointment_required(self):
    #     for rec in self:
    #         rec.appointment_required = rec.delivery_address_id.appointment_required
    #
    # @api.depends('delivery_address_id', 'delivery_address_id.residential')
    # def set_residential(self):
    #     for rec in self:
    #         rec.residential_address = rec.delivery_address_id.residential

    liftgate_required = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Liftgate Required?",
                                         compute='_compute_liftgate_required_from_delivery_partner_id')
    appointment_required = fields.Selection([('yes', 'Yes'), ('no', 'No')],
                                            string="Appointment Required?",
                                            compute='_compute_appointment_required_from_delivery_partner_id')
    residential_address = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Residential Address?",
                                           compute='_compute_resedential_from_delivery_partner_id')

    @api.depends('delivery_address_id', 'delivery_address_id.liftgate_required')
    def _compute_liftgate_required_from_delivery_partner_id(self):
        for rec in self:
            if rec.delivery_address_id:
                rec.liftgate_required = rec.delivery_address_id.liftgate_required
            else:
                rec.liftgate_required = False

    @api.depends('delivery_address_id', 'delivery_address_id.appointment_required')
    def _compute_appointment_required_from_delivery_partner_id(self):
        for rec in self:
            if rec.delivery_address_id:
                rec.appointment_required = rec.delivery_address_id.appointment_required
            else:
                rec.appointment_required = False

    @api.depends('delivery_address_id', 'delivery_address_id.residential')
    def _compute_resedential_from_delivery_partner_id(self):
        for rec in self:
            if rec.delivery_address_id:
                rec.residential_address = 'yes' if rec.delivery_address_id.residential else 'no'
            else:
                rec.residential_address = False
