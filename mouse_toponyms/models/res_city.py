# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class City(models.Model) :
    _inherit = 'res.city'
    
    state_id = fields.Many2one(required=True)
    
    @api.onchange('country_id')
    def _onchange_country_id(self):
        if self.state_id :
            self.state_id = False
    
    _sql_constraints = [('unique_district_name', 'unique(country_id, state_id, name)', '¡Esta ciudad ya existe!\nIntente cambiar la provincia.'),
                        ('unique_district_code', 'unique(country_id, state_id, l10n_pe_code)', '¡Ya existe una ciudad con este código en esta provincia!')]
