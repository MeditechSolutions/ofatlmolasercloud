# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class EinvoiceTmpl(models.Model) :
    _name = 'einvoice.tmpl'
    _description = 'Plantilla de Códigos de la SUNAT'
    
    code = fields.Char(string='Código', index=True, required=True)
    name = fields.Char(string='Nombre', index=True, required=True)
    
    @api.depends('code', 'name')
    def name_get(self) :
        return [(rec.id, rec.code and (rec.code + ' - ' + rec.name) or rec.name) for rec in self]

#Model: l10n_latam.document.type
#class Einvoice01(models.Model) :
#    _name = 'einvoice.01'
#    _description = 'Código de Tipo de Documento'
#    _inherit = 'einvoice.tmpl'
#    
#    label = fields.Char(string='Label to print')

#Model: account.tax; l10n_pe_edi_tax_code, l10n_pe_edi_unece_category
#class Einvoice05(models.Model) :
#    _name = "einvoice.05"
#    _description = 'Código de Tipo de Tributo'
#    _inherit = 'einvoice.tmpl'
#    
#    un_5153 = fields.Char(string='UN/ECE 5153-Duty or tax or fee type name code')
#    un_5103 = fields.Char(string='UN/ECE 5305-Duty or tax or fee category code')
#    tax_name = fields.Char(string='Tax Name')

#Model: l10n_latam.identification.type
#class Einvoice06(models.Model) :
#    _name = "einvoice.06"
#    _description = 'Código de Tipo de Documento de Identidad'
#    _inherit = 'einvoice.tmpl'
#    
#    default = fields.Char(string='Default value')

class Einvoice07(models.Model) :
    _name = "einvoice.07"
    _description = 'Códigos de Tipo de Afectación del IGV'
    _inherit = 'einvoice.tmpl'
    
    name = fields.Char(string='Tipo de IGV')
    onerosa = fields.Boolean(string='Operación Onerosa')
    type = fields.Selection(string='Tipo de Afectación', selection=[('gravado','Gravado'),('exonerado','Exonerado'),('inafecto','Inafecto')])

class Einvoice09(models.Model) :
    _name = "einvoice.09"
    _description = 'Códigos de Tipo de Nota de Crédito Electrónica'
    _inherit = 'einvoice.tmpl'
    
    name = fields.Char(string='Tipo de Nota de Crédito')

class Einvoice10(models.Model) :
    _name = "einvoice.10"
    _description = 'Códigos de Tipo de Nota de Débito Electrónica'
    _inherit = 'einvoice.tmpl'
    
    name = fields.Char(string='Tipo de Nota de Débito')

#Model: account.tax; l10n_pe_edi_unece_category ???
#class Einvoice11(models.Model) :
#    _name = "einvoice.11"
#    _description = 'Código de Tipo de Valor de Venta'
#    _inherit = 'einvoice.tmpl'

class Einvoice51(models.Model) :
    _name = "einvoice.51"
    _description = 'Código de Tipo de Operación'
    _inherit = 'einvoice.tmpl'
    
    name = fields.Char(string='Tipo de Operación')
