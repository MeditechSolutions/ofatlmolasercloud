# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class Partner(models.Model):
    _inherit = "res.partner"
    
    street_name = fields.Char(compute=False, inverse=False)
    street_number = fields.Char(compute=False, inverse=False)
    street_number2 = fields.Char(compute=False, inverse=False)
    
    #Override the original onchange functions of base and l10n_latam_base with super()
    @api.onchange('country_id')
    def _onchange_country(self) :
        super(models.Model, self)
        if self.state_id :
            self.state_id = False
        else :
            self.zip = False
    
    @api.onchange('country_id')
    def _onchange_country_id(self):
        m = self.country_id
    
    @api.onchange('state_id')
    def _onchange_state(self) :
        super(models.Model, self)
        if self.city_id :
            self.city_id = False
        else :
            self.zip = self.state_id.code
    
    @api.onchange('city_id')
    def _onchange_city_id(self) :
        super(models.Model, self)
        self.city = self.city_id.name
        if self.l10n_pe_district :
            self.l10n_pe_district = False
        else :
            self.zip = self.city_id.l10n_pe_code or self.state_id.code
    
    @api.onchange('l10n_pe_district')
    def _onchange_l10n_pe_district(self) :
        self.zip = self.l10n_pe_district.code or self.city_id.l10n_pe_code or self.state_id.code
    
    def write(self, vals):
        res = super(Partner, self).write(vals)
        if 'street' not in vals and ('street_name' in vals or 'street_number' in vals or 'street_number2' in vals) :
            self._set_street()
        return res
    
    # New functions for the new fields
    @api.model
    def _address_fields(self):
        """ Returns the list of address fields that are synced from the parent """
        address_fields = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id', 'city_id', 'l10n_pe_district')
        return list(address_fields)
    
    def _display_address(self, without_company=False) :
        '''
        The purpose of this function is to build and return an address formatted accordingly to the
        standards of the country where it belongs.
        
        :param address: browse record of the res.partner to format
        :returns: the address formatted in a display that fit its country habits (or the default ones
            if not country is specified)
        :rtype: string
        '''
        # get the information that will be injected into the display format
        # get the address format
        address_format = self.country_id.id == 173 and "%(street)s\n%(district_name)s - %(city_name)s - %(state_name)s - %(zip)s\n%(country_name)s" or self._get_address_format()
        args = {
            'district_code': self.l10n_pe_district.code or '',
            'district_name': self.l10n_pe_district.name or '',
            'city_code': self.city_id.l10n_pe_code or '',
            'city_name': self.city_id.name or '',
            'state_code': self.state_id.code or '',
            'state_name': self.state_id.name or '',
            'country_code': self.country_id.code or '',
            'country_name': self.country_id.name or '',
            'company_name': self.parent_name or '',
        }
        for field in self._formatting_address_fields():
            args[field] = getattr(self, field) or ''
        if without_company:
            args['company_name'] = ''
        elif self.mapped('commercial_company_name') :
            address_format = '%(company_name)s\n' + address_format
        return address_format % args
