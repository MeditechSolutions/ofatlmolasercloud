# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class Company(models.Model) :
    _inherit = 'res.company'
    
    def write(self, values) :
        res = super(Company, self).write(values)
        if self.partner_id.country_id and self.env.ref('base.pe') in self.partner_id.country_id :
            self.env['res.currency.rate'].sudo().calcular_tasa_dolar_euro_bcr()
        return res
