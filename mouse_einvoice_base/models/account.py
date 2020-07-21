# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class AccountJournal(models.Model) :
    _inherit = "account.journal"
    
    l10n_latam_document_type_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Tipo de documento')
    l10n_latam_document_type_credit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Tipo de nota de crédito')
    l10n_latam_document_type_debit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Tipo de nota de débito')
    
    #@api.model
    #def _create_sequence(self, vals, refund=False) :
    #    """For Peruvian companies, a number reset by date do not make sense due to the fact that we can not use a free
    #    prefix the format does not have enough space to put a year on it or any other char, then with this approach we
    #    are avoiding the default behavior there."""
    #    res = super(AccountJournal, self)._create_sequence(vals, refund=refund)
    #    # NOTE: the self element is coming filled just when write and not on create (which is Ok)
    #    if self.env.company.country_id == self.env.ref('base.pe', False) and vals.get('type', self.type) in ['sale', 'purchase']:
    #        res.write({'padding': 8, 'l10n_latam_journal_id': self.id})
    #    return res
    
    @api.model
    def create(self, vals) :
        res = super(AccountJournal, self).create(vals)
        if res.company_id.country_id == self.env.ref('base.pe', False) and res.type in ['sale', 'purchase'] :
            res.sequence_id.write({'padding': 8, 'l10n_latam_journal_id': self.id})
        return res

class AccountTax(models.Model):
    _inherit = 'account.tax'
    
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
