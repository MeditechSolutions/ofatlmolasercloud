# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class AccountTaxTemplate(models.Model):
    _inherit = 'account.tax.template'
    
    l10n_pe_edi_tax_code = fields.Selection(selection=[
        ('1000', 'IGV - VAT - Impuesto General a las Ventas'),
        ('1016', 'IVAP - VAT - Impuesto a la Venta Arroz Pilado'),
        ('2000', 'ISC - EXC - Impuesto Selectivo al Consumo'),
        ('9995', 'EXP - FRE - Exportación'),
        ('9996', 'GRA - FRE - Gratuito'),
        ('9997', 'EXO - VAT - Exonerado'),
        ('9998', 'INA - FRE - Inafecto'),
        ('9999', 'OTROS - OTH - Otros tributos')
    ], string='Código SUNAT EDI')
    
    l10n_pe_edi_unece_category = fields.Selection(string='Código UNECE 5305')
