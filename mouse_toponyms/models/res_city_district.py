# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class L10nPeResCityDistrict(models.Model) :
    _inherit = 'l10n_pe.res.city.district'
    
    name = fields.Char(required=True)
    country_id = fields.Many2one(comodel_name="res.country", string="País", required=True)
    state_id = fields.Many2one(comodel_name="res.country.state", string="Provincia", required=True)
    city_id = fields.Many2one(required=True)
    code = fields.Char(required=True)
    
    _sql_constraints = [('unique_district_name', 'unique(city_id, name)', '¡Este distrito ya existe!\nIntente cambiar la provincia o la ciudad.'),
                        ('unique_district_code', 'unique(city_id, code)', '¡Ya existe un distrito con este código en este país!\nIntente cambiar el país, la provincia o la ciudad.')]
