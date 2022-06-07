# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class ResCompany(models.Model):    
    _inherit = 'res.company'
    
    ftp_server = fields.Char('FTP Server')
    ftp_port = fields.Integer('FTP Port')
    ftp_user = fields.Char('FTP User')
    ftp_secret = fields.Char('FTP Secret')
    ftp_gpath = fields.Char('FTP Grab Path') # the path where you get from files
    ftp_dpath = fields.Char('FTP Drop Path') # the path where you put to files
    ftp_tls = fields.Boolean('FTP TLS Enabled', default=True)
    enable_cron = fields.Boolean('Enable cron', default=False)
