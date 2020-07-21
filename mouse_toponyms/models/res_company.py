# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class Company(models.Model):
    _inherit = "res.company"
    
    city_id = fields.Many2one(comodel_name="res.city", compute='_compute_address', inverse='_inverse_city', string="Ciudad")
    l10n_pe_district = fields.Many2one(comodel_name="l10n_pe.res.city.district", compute='_compute_address', inverse='_inverse_district', string="Distrito")
    
    def _get_company_address_fields(self, partner):
        address_fields = super(Company, self)._get_company_address_fields(partner)
        address_fields.update({
            'city_id': partner.city_id,
            'l10n_pe_district': partner.l10n_pe_district,
        })
        return address_fields
    
    @api.onchange('country_id')
    def _onchange_country_id_wrapper(self):
        if self.state_id :
            self.state_id = False
        else :
            self.zip = False
        return super(Company, self)._onchange_country_id_wrapper()
    
    #Override the original onchange function
    @api.onchange('state_id')
    def _onchange_state(self):
        super(models.Model, self)
        if self.city_id :
            self.city_id = False
        else :
            self.zip = self.state_id.code
    
    @api.onchange('city_id')
    def _onchange_city_id(self) :
        self.city = self.city_id.name
        if self.l10n_pe_district :
            self.l10n_pe_district = False
        else :
            self.zip = self.city_id.l10n_pe_code or self.state_id.code
    
    @api.onchange('l10n_pe_district')
    def _onchange_l10n_pe_district(self) :
        self.zip = self.l10n_pe_district.code or self.city_id.l10n_pe_code or self.state_id.code

    def _inverse_city(self):
        for company in self:
            company.partner_id.city_id = company.city_id

    def _inverse_district(self):
        for company in self:
            company.partner_id.l10n_pe_district = company.l10n_pe_district
