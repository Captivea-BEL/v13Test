# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError, MissingError, ValidationError
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from json import dumps


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('kuebix', 'Kuebix')])
    

    def get_kuebix_rates(self, order):
        # Method to get rates
        result = False
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
            try:
                url = "https://shipment.kuebix.com/api/action/quickRate"
                auth_str = HTTPBasicAuth(
                    order.company_id.username,
                    order.company_id.password)
                headers = {
                    'Content-Type': "application/json",
                    'cache-control': "no-cache",
                }

                lineItems = []
                handlingUnits = []
                for line in order.order_line:
                    if not line.product_id or line.is_delivery:
                        continue
                    lineItems.append({
                        "sku": line.product_id.default_code,
                        "packageType": "Box(es)",
                        "weight": line.product_id.weight,
                        "quantity": line.product_uom_qty,
                        "freightClass": line.product_id.freight_class
                    })
                handlingUnits.append({
                    "weight": sum(o_line.product_id.weight * o_line.product_uom_qty for o_line in order.order_line),
                    "hutype": "Carton(s)",
                    "quantity": 1,
                    "weightUnit": "LB",
                })
                total_weight = 0.0
                for line in order.order_line:
                    if line.product_id.weight and line.product_id.weight > 0.0:
                        total_weight += (line.product_id.weight * line.product_uom_qty)
                    if line.product_id.type in ('product','consu') and line.product_id.weight == 0.0:
                        raise Warning((line.product_id.name)+" does not have a weight, schedule an activity to update the weight of the product in Odoo or contact the appropriate user to update the product data")
                    if total_weight > 135.0:
                        raise Warning(_("The weight limit is over 135 lbs, schedule an activity to request an LTL quote"))
                    if total_weight < 1.0:
                        total_weight = 1.0
                if order.paymenttype not in ('outbound_prepaid','third_party'):
                    raise Warning(_("The Payment Type must be 'Outbound Prepaid' or 'Third Party'.  Please change the Sales Quote accordingly and click on 'FETCH ALL CARRIERS' button"))
                if not order.client_order_ref:
                    raise Warning(_("Please enter the Customer PO reference. If there is no Customer PO Reference, please enter 'No Customer PO' !"))
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
                            order.company_id.partner_id.street,
                        "streetAddress2":
                            order.company_id.partner_id.street2,
                        "postalCode": order.company_id.partner_id.zip,
                        "contact": {
                            "name": order.company_id.partner_id.name,
                            "email": order.company_id.partner_id.email
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
                        "streetAddress": order.partner_shipping_id.street,
                        "postalCode": order.partner_shipping_id.zip,
                        "contact": {
                            "name": order.partner_shipping_id.name,
                            "email": order.partner_shipping_id.email
                        }
                    },
                    "billTo": {
                        "companyName": order.company_id.partner_id.name,
                        "country":
                            order.company_id.partner_id.country_id.name,
                        "stateProvince":
                            order.company_id.partner_id.state_id.code,
                        "city": order.company_id.partner_id.city,
                        "streetAddress": order.company_id.partner_id.street,
                        "postalCode": order.company_id.partner_id.zip,
                        "contact": {
                            "name": order.company_id.partner_id.name,
                            "email": order.company_id.partner_id.email
                        }
                    },
                    "client": {
                        "id": order.company_id.client_id,
                    },
                    "lineItems": lineItems,
                    "handlingUnits": handlingUnits,
                    "weightUnit": "LB",
                    "lengthUnit": "IN",
                    "shipmentType": dict(order._fields['shipment_type'].selection).get(order.shipment_type),
                    "shipmentMode": dict(order._fields['shipment_mode'].selection).get(order.shipment_mode),
                    "paymentType": dict(order._fields['paymenttype'].selection).get(order.paymenttype),
                }
                response = requests.post(url, headers=headers,
                                         auth=auth_str, json=payload)
                if response.status_code == 400:
                    raise Warning(_("Incorrect Request: incorrect information on the Sales Order, please correct the data and select Fetch Rate again!"))
                if response.status_code == 401:
                    raise Warning(_("Incorrect kuebix credentials: please contact your administrator to change the kuebix credentials!"))
                # if response.status_code == 500:
                #     raise Warning(_(""))
                result = response.json()

            except Exception as e:
                raise UserError(_('Internal Kuebix Server Error. Please contact the Kuebix sales representative!'))

        return result

    def kuebix_send_shipping(self, pickings):
        res = []
        for picking in pickings:
            order = self.env['sale.order'].sudo().search([('name', '=', str(picking.origin))], limit=1)
            shipment_id = picking.shipment_id
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
                            shipping_data = { 'exact_price': result['bookedRateQuote']['totalPrice'],
                                    'tracking_number': result['proNumber']}
                            res = res + [shipping_data]
                    except Exception as e:
                        raise UserError(_('%s') % str(e))
                return res
        return result
