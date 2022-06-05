

from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):

    _inherit = "res.config.settings"

    ar_discount_account = fields.Many2one("account.account", string="AR Discount Account", config_parameter="cap_custom_register_payment.default_ar_discount_account")
    ap_discount_account = fields.Many2one("account.account", string="AP Discount Account", config_parameter="cap_custom_register_payment.default_ap_discount_account")

