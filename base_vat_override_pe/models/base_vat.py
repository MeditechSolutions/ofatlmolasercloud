# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, Warning

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    def check_vat_pe(self, vat):
        res = super(ResPartner, self).check_vat_pe(vat)
        if not res and vat.isdigit() and len(vat) != 11 :
            res = True
        return res
