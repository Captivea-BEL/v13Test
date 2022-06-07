# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import time
import pysftp
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _name = 'setu.sftp'
    _description='SFTP Server Configuration and Details'
    _rec_name = 'company_id'

    default_instance = fields.Boolean(default=False)
    instance_active = fields.Boolean()
    company_id = fields.Many2one('res.company', string='Company', required=True)
    ftp_server = fields.Char('FTP Server', required=True)
    ftp_port = fields.Integer('FTP Port', default='22', required=True)
    ftp_user = fields.Char('FTP User', required=True, copy=False)
    ftp_secret = fields.Char('FTP Secret', required=True, copy=False)
    ftp_gpath = fields.Char('FTP 850 Path', required=True)  # the path where you get from files
    ftp_poack_dpath = fields.Char('FTP 855 Drop Path', required=True)  # the path where you put to files
    ftp_shipack_dpath = fields.Char('FTP 856 Drop Path', required=True)
    ftp_invack_dpath = fields.Char('FTP 810 Drop Path', required=True)
    ftp_tls = fields.Boolean('FTP TLS Enabled', default=True)
    enable_cron = fields.Boolean('Enable Automated Process', default=False)
    ir_cron_id = fields.Many2one('ir.cron', string='Configure Automated Process')

    @api.constrains('instance_active')
    def validate_instance(self):
        if self.search(
                [('id', '!=', self.id), ('company_id', '=', self.company_id.id),
                 ('instance_active', '=', True)]) and self.instance_active:
            raise ValidationError(_("Company's one Configuration is already active."))

    @api.onchange('default_instance')
    def validate_default_instant(self):
        """
        It will False all values except current sftp instance.
        @return:
        """
        if self.default_instance:
            self.search([]).default_instance = False


    def test_connection(self):
        """
        It will test sftp connection.
        @return: sftp : return sftp object if successful.
                 status : return sftp status.
        """
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        for x in range(2):
            try:
                sftp = pysftp.Connection(host=self.ftp_server, username=self.ftp_user, password=self.ftp_secret,
                                         port=self.ftp_port,
                                         cnopts=cnopts)
                if sftp:
                    return sftp, 'pass'

            except Exception as e:
                time.sleep(2)
                continue

        return False, 'Invalid Server Details or Connection Lost'
