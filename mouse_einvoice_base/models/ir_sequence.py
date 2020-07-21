# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class IrSequence(models.Model) :
    _inherit = "ir.sequence"
    
    l10n_latam_document_type_id = fields.Many2one(related="l10n_latam_journal_id.l10n_latam_document_type_id")
    l10n_latam_document_type_credit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Tipo de nota de crédito', related="l10n_latam_journal_id.l10n_latam_document_type_credit_id")
    l10n_latam_document_type_debit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Tipo de nota de débito', related="l10n_latam_journal_id.l10n_latam_document_type_debit_id")
