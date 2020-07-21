# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class einvoice_catalog_06(models.Model):
    _inherit = "l10n_latam.identification.type"
    
    l10n_pe_vat_code = fields.Char(string="Código SUNAT")
    
    @api.depends('l10n_pe_vat_code', 'name')
    def name_get(self):
        #result = []
        #for table in self:
        #    l_name = table.code and table.code+' - ' or ''
        #    l_name +=  table.name
        #    result.append((table.id, l_name ))
        #return result
        return [(record.id, (record.l10n_pe_vat_code and record.l10n_pe_vat_code + ' - ' or '') + record.name) for record in self]
