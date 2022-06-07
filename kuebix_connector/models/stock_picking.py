

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, Warning, MissingError
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from json import dumps
from werkzeug.urls import url_encode

import logging
_logger = logging.getLogger(__name__)

class Picking(models.Model):
    
    _inherit = 'stock.picking'
    
    picking_type_name = fields.Char(related="picking_type_id.name")
    liftgate_required = fields.Selection([('yes','Yes'),('no','No')], string="Liftgate Required?")
    residential = fields.Boolean(default=False, string="Residential Address?")
    appointment_required = fields.Selection([('yes','Yes'),('no','No')], default=False, string="Appointment Required?")
    shipping_service = fields.Char(string="Shipping Service")
    shipment_type = fields.Selection([('parcel','Parcel'),('ltl','LTL'),('tl','TL')], string="Type of Shipment", help = 'True if the order is shipped via Parcel')
    actual_shipping_cost = fields.Float(string = "Actual Shipping Cost")
    weight_for_shipping = fields.Float(string="Shipping Weight")
    kuebix_processed = fields.Boolean(string="Kuebix Shipment Processed")
    shipment_id = fields.Char(string="Shipment ID")
    other_tracking_numbers = fields.Text(string="Additional Tracking Numbers")
    shipment_name = fields.Char(string="Shipment Name")
    service_type = fields.Char(string="Service Type")
    x_scac_kuebix = fields.Char(string="SCAC")
    bol_number = fields.Char(string="BOL Number")
    k_type_of_picking = fields.Char(related='picking_type_id.sequence_code')
    
    is_shipment_id_set = fields.Boolean("Is Shipment Set?", compute="_comute_shipment_set")
    
    @api.depends("shipment_id")
    def _comute_shipment_set(self):
        for rec in self:
            if rec.shipment_id:
                rec.is_shipment_id_set = True
            else:
                rec.is_shipment_id_set = False

    # @api.onchange('x_scac_kuebix')
    # def _onchange_x_scac_kuebix(self):
        # for rec in self:
            # rec.x_scac = rec.x_scac_kuebix

    @api.onchange('carrier_id','x_scac_kuebix')
    def _onchange_carrier_id(self):
        for rec in self:
            if rec.carrier_id and rec.carrier_id.delivery_type != "kuebix":
                rec.x_studio_scac = rec.carrier_id.x_scac
            elif rec.carrier_id and rec.carrier_id.delivery_type == "kuebix":
                rec.x_studio_scac = rec.x_scac_kuebix

    @api.model
    def create(self, vals):
        if vals['origin']:
            order = self.env['sale.order'].sudo().search([('name', '=', str(vals['origin']))], limit=1)
            if order.kuebix_carrier_id:
                vals['shipment_type'] = 'parcel'
            else:
                vals['shipment_type'] = None
            if order.liftgate_required:
                vals['liftgate_required'] = order.liftgate_required
            if order.residential:
                vals['residential'] = order.residential
            if order.appointment_required:
                vals['appointment_required'] = order.appointment_required
            if order.shipping_service_quote:
                vals['shipping_service'] = order.shipping_service_quote
        return super(Picking, self).create(vals)

    # def button_validate(self):
    #     res = super(Picking, self).button_validate()
    #     order = self.env['sale.order'].sudo().search([('name', '=', str(self.origin))], limit=1)
    #     if self.picking_type_id.name == 'Pack':
    #         shipment = self._create_kuebix_shipment(order)
    #         for pick in order.picking_ids:
    #             pick.shipment_id = shipment['shipmentId']
    #             pick.shipment_name = shipment['shipmentName']
    #             pick.kuebix_processed = True
    #     return res
    
    
    def create_kuebix_shipment(self):
        result = False
        order = self.env['sale.order'].sudo().search([('name', '=', str(self.origin))], limit=1)
        if not order.company_id.username or \
                not order.company_id.password \
                or not order.company_id.client_id:
            raise MissingError(_(
                'Something is missing Username, Password or Client ID'))
        elif not order.partner_shipping_id.country_id or \
                not order.partner_shipping_id.zip:
            raise MissingError(_('Please enter proper delivery address '
                                 'details.'))
        elif not order.company_id.partner_id.country_id or \
                not order.company_id.partner_id.zip:
            raise MissingError(
                _('Please enter proper warehouse address details.'))
        elif self.kuebix_processed == True:
            raise Warning(_("Shipment is Already processed for this order!"))
        else:
            try:
                url = "https://shipment.kuebix.com/api/shipments"
                auth_str = HTTPBasicAuth(
                    order.company_id.username,
                    order.company_id.password)
                headers = {
                    'Content-Type': "application/json",
                    'cache-control': "no-cache",
                }
                lineItems = []
                handlingUnits = []
                packages = []
                unique_result_package_ids_list = []
                unique_shipping_packages_list = []
                shipping_packages = self.move_line_ids_without_package.mapped('shipping_package')
                if shipping_packages:
                    # LTL API call item details
                    ship_pack_dict = {}
                    for ship_pack in shipping_packages:
                        mv_line_list = []
                        for mv_line in self.move_line_ids_without_package.filtered(lambda mvl: mvl.shipping_package.id == ship_pack.id):
                            mv_line_list.append(mv_line)
                        ship_pack_dict.update({ship_pack:mv_line_list})
                    for k,v in ship_pack_dict.items():
                        # LTL API call item details
                        lineItems.append({
                            "packageReference": k.name,
                            "packageType": "Box(es)",
                            "description": "Magnets",
                            "weight": 9999,
                            "freightClass": "77.5",
                            "poNumber": order.client_order_ref
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
                elif not shipping_packages:
                    for move_line in self.move_line_ids_without_package:
                        # if not move_line.shipping_package and (move_line.result_package_id and move_line.result_package_id.id not in unique_result_package_ids_list):
                        # if (move_line.shipping_package or move_line.result_package_id) and self.shipment_type == 'parcel':
                        # Parcel API call item details
                        lineItems.append({
                            "packageReference": move_line.result_package_id.name,
                            "packageType": "Box(es)",
                            "description": "Magnets",
                            "weight": 9999,
                            "freightClass": "77.5",
                            "poNumber": order.client_order_ref
                        })
                        handlingUnits.append({
                            "reference": move_line.result_package_id.name,
                            "huType": "Box(es)",
                            "quantity": 1,
                            "weight": 9999,
                            "length": 48,
                            "width": 40,
                        })
                        packages.append({
                            "quantity": 1,
                            "weight": 9999,
                            "length": 48,
                            "width": 40,
                            "reference": move_line.result_package_id.name,
                            "handlingUnitReference": move_line.result_package_id.name,
                        })
                        unique_result_package_ids_list.append(move_line.result_package_id.id)
                # Parcel
                payload = {
                    "origin": {
                        "companyName":
                            order.company_id.partner_id.name,
                        "country":
                            order.company_id.partner_id.country_id.name,
                        "stateProvince":
                            order.company_id.partner_id.state_id.code,
                        "city": order.company_id.partner_id.city,
                        "streetAddress":
                            order.company_id.partner_id.street + (order.company_id.partner_id.street2 or ''),
                        "postalCode": order.company_id.partner_id.zip,
                        "contact": {
                            "name": order.company_id.partner_id.name,
                            "email": order.company_id.partner_id.email or '',
                        },
                        "notes": "Example note"
                    },
                    "destination": {
                        "companyName": order.partner_shipping_id.name,
                        "country":
                            order.partner_shipping_id.country_id.name,
                        "stateProvince":
                            order.partner_shipping_id.state_id.code,
                        "city": order.partner_shipping_id.city,
                        "streetAddress": order.partner_shipping_id.street + (order.company_id.partner_id.street2 or ''),
                        "postalCode": order.partner_shipping_id.zip,
                        "contact": {
                            "name": order.partner_shipping_id.name,
                            "email": order.partner_shipping_id.email or '',
                        }
                    },
                    "billTo": {
                        "companyName": order.company_id.partner_id.name,
                        "country":
                            order.company_id.partner_id.country_id.name,
                        "stateProvince":
                            order.company_id.partner_id.state_id.code,
                        "city": order.company_id.partner_id.city,
                        "streetAddress": order.company_id.partner_id.street + (order.company_id.partner_id.street2 or ''),
                        "postalCode": order.company_id.partner_id.zip,
                        "contact": {
                            "name": order.company_id.partner_id.name,
                            "email": order.company_id.partner_id.email or '',
                        }
                    },
                    "client": {
                        "id": order.company_id.client_id,
                    },
                    "lineItems": lineItems,
                    "handlingUnits": handlingUnits,
                    "packages": packages,
                    "weightUnit": "LB",
                    "lengthUnit": "IN",
                    "shipmentType": dict(self._fields['shipment_type'].selection).get(self.shipment_type) or '',
                    "shipmentMode": "Dry Van",
                    "paymentType": dict(order._fields['paymenttype'].selection).get(order.paymenttype) or '',
                    "bolNumber": order.name,
                    "poNumbers": order.client_order_ref,
                    "soNumbers": order.name,
                }
                response = requests.post(url, headers=headers,
                                         auth=auth_str, json=payload)
                if response.status_code == 400:
                    raise UserError(_("Incorrect Request: incorrect information on the Transfer, please correct the data and validate the Transfer!"))
                if response.status_code == 401:
                    raise UserError(_("Incorrect Kuebix credentials: please contact an Administrator to change the Kuebix credentials!"))
                # if response.status_code == 500:
                #     raise UserError(_(""))
                result = response.json()
                for pick in order.picking_ids:
                    pick.shipment_id = result['shipmentId']
                    pick.shipment_name = result['shipmentName']
                    pick.kuebix_processed = True
            except Exception as e:
                raise UserError(_('Internal Kuebix Server Error. Please contact the Kuebix sales representative!'))

        return result
    
    def delete_kuebix_shipment(self):
        order = self.env['sale.order'].sudo().search([('name', '=', str(self.origin))], limit=1)
        for rec in self:
            if rec.shipment_id and rec.shipment_name:
                try:
                    url = "https://shipment.kuebix.com/api/shipments/%s"%(rec.shipment_id)
                    auth_str = HTTPBasicAuth(
                        order.company_id.username,
                        order.company_id.password)
                    headers = {
                        'Content-Type': "application/json",
                        'cache-control': "no-cache",
                    }
                    response = requests.delete(url, auth=auth_str)
                    result = response.json()
                    for pick in order.picking_ids:
                        pick.shipment_id = ''
                        pick.shipment_name = ''
                        pick.kuebix_processed = False
                except Exception as e:
                    raise UserError(_('%s') % str(e))
    
    def import_shipping_detail(self):
        result = False
        order = self.env['sale.order'].sudo().search([('name', '=', str(self.origin))], limit=1)
        shipment_id = self.shipment_id
        if not order.company_id.username or \
                not order.company_id.password \
                or not order.company_id.client_id:
            raise MissingError(_(
                'Something is missing Username, Password or Client ID'))
        elif not order.partner_shipping_id.country_id or \
                not order.partner_shipping_id.zip:
            raise MissingError(_('Please enter proper delivery address '
                                 'details.'))
        elif not order.company_id.partner_id.country_id or \
                not order.company_id.partner_id.zip:
            raise MissingError(
                _('Please enter proper warehouse address details.'))
        else:
            if shipment_id:
                try:
                    url = "https://shipment.kuebix.com/api/shipments/%s"%(shipment_id)
                    auth_str = HTTPBasicAuth(
                        order.company_id.username,
                        order.company_id.password)
                    headers = {
                        'Content-Type': "application/json",
                        'cache-control': "no-cache",
                    }
                    response = requests.get(url, auth=auth_str)
                    result = response.json()
                    if result:
                        # print ("result --->>", result['lineItems'])
                        # total_weight = 0.0
                        # for lineitems in result['lineItems']:
                        #     total_weight += lineitems['weight']
                        self.actual_shipping_cost = result['bookedRateQuote']['totalPrice'] if not self._context.get('batch_ship') else 0.0 
                        shipment_type_dict = dict(self._fields['shipment_type'].selection)
                        self.shipment_type = list(shipment_type_dict.keys())[list(shipment_type_dict.values()).index(result['shipmentType'])]
                        self.x_scac_kuebix = result['bookedRateQuote']['scac']
                        self.x_studio_scac = result['bookedRateQuote']['scac']
                        self.shipping_service = result['bookedRateQuote']['carrierName']
                        self.bol_number = result['bolNumber']
                        self.carrier_tracking_ref = result['proNumber']
                        kuebix_carrier_id = self.env['delivery.carrier'].search([('delivery_type','=','kuebix')], limit=1)
                        self.carrier_id = kuebix_carrier_id.id
                        # self.weight = total_weight
                        # self.shipping_weight = total_weight
                except Exception as e:
                    raise UserError(_('Please complete the shipment in Kuebix before importing the details'))
            return result
        return result

    def action_get_bol(self):
        order = self.env['sale.order'].sudo().search([('name', '=', str(self.origin))], limit=1)
        if not order.company_id.username or \
                not order.company_id.password \
                or not order.company_id.client_id:
            raise MissingError(_(
                'Something is missing Username, Password or Client ID'))
        elif not order.partner_shipping_id.country_id or \
                not order.partner_shipping_id.zip:
            raise MissingError(_('Please enter proper delivery address '
                                 'details.'))
        elif not order.company_id.partner_id.country_id or \
                not order.company_id.partner_id.zip:
            raise MissingError(
                _('Please enter proper warehouse address details.'))
        elif not self.bol_number:
            raise Warning(_('Please Import Shipping Details First!'))
        else:
            try:
                url = "https://shipment.kuebix.com/api/shipments/docs/bol"
                auth_str = HTTPBasicAuth(
                    order.company_id.username,
                    order.company_id.password)
                headers = {
                    'Content-Type': "application/json",
                    'cache-control': "no-cache",
                }
                payload = {
                    'shipmentId': self.shipment_id,
                }
                response = requests.post(url, headers=headers,
                                         auth=HTTPBasicAuth(order.company_id.username,order.company_id.password), json=payload)
                if response.status_code == 400:
                    raise UserError(_("Incorrect Request: incorrect information on the Delivery Order, please correct the data and try again!"))
                if response.status_code == 401:
                    raise UserError(_("Incorrect kuebix credentials: please contact your administrator to change the kuebix credentials!"))
                # if response.status_code == 500:
                #     raise UserError(_(""))
                result = response.json()
                if not self._context.get('batch_picking_operation'):
                    self.weight_for_shipping = result.get('weightTotal')
                base64_string = bytes(result['base64String'], 'utf-8')
                if base64_string:
                    pdf = self.env['ir.attachment'].create({
                        'name': 'bill_of_lading.pdf',
                        'type': 'binary',
                        'datas': base64_string,
                        'store_fname': "bill_of_lading" + ".pdf",
                        'res_model': 'stock.picking',
                        'res_id': self._origin.id,
                        'mimetype': 'application/x-pdf'
                    })
            except Exception as e:
                raise UserError(_('Internal Kuebix Server Error. Please contact the Kuebix sales representative!'))

        return result

    def action_get_tracking(self):
        order = self.env['sale.order'].sudo().search([('name', '=', str(self.origin))], limit=1)
        if not order.company_id.username or \
                not order.company_id.password \
                or not order.company_id.client_id:
            raise MissingError(_(
                'Something is missing Username, Password or Client ID'))
        elif not order.partner_shipping_id.country_id or \
                not order.partner_shipping_id.zip:
            raise MissingError(_('Please enter proper delivery address '
                                 'details.'))
        elif not order.company_id.partner_id.country_id or \
                not order.company_id.partner_id.zip:
            raise MissingError(
                _('Please enter proper warehouse address details.'))
        elif not self.bol_number:
            raise Warning(_('Please Import Shipping Details First!'))
        else:
            try:
                url = "https://apis.kuebix.com/v2/shipment/track"
                auth_str = HTTPBasicAuth(
                    order.company_id.username,
                    order.company_id.password)
                headers = {
                    'Content-Type': "application/json",
                    'cache-control': "no-cache",
                }
                payload = {
                    'kuebixBOLs': self.bol_number,
                }
                response = requests.get(url, auth=auth_str, params=payload)
                if response.status_code == 400:
                    raise Warning(_("Incorrect Request: incorrect information on the Delivery Order, please correct the data and try again!"))
                if response.status_code == 401:
                    raise Warning(_("Incorrect kuebix credentials: please contact your administrator to change the kuebix credentials!"))
                # if response.status_code == 500:
                #     raise Warning(_(""))
                result = response.json()
            except Exception as e:
                raise UserError(_('Internal Kuebix Server Error. Please contact the Kuebix sales representative!'))

        return result
