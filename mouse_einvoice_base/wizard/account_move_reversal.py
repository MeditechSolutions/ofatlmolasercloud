# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class AccountMoveReversal(models.TransientModel) :
    """
    Account move reversal wizard, it cancel an account move by reversing it.
    """
    _inherit = 'account.move.reversal'
    
    l10n_latam_document_type_id = fields.Many2one(related="journal_id.l10n_latam_document_type_id")
    journal_id = fields.Many2one(required=True)
    
    def _prepare_default_reversal(self, move) :
        res = super(AccountMoveReversal, self)._prepare_default_reversal(move)
        res.update({'credit_origin_id': move.id, 'einvoice_journal_id': res['journal_id']})
        return res
