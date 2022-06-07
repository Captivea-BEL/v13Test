# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = "product.template"

    def name_get(self):
        context = self._context or {}
        if context.get('mrp_bom'):
            self.browse(self.ids).read(['name', 'default_code'])
            return [(template.id, '%s' % (template.name)) for template in self]
        return super(ProductTemplate, self).name_get()
