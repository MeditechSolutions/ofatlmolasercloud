# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class AccountDebitNote(models.TransientModel) :
    """
    Add Debit Note wizard: when you want to correct an invoice with a positive amount.
    Opposite of a Credit Note, but different from a regular invoice as you need the link to the original invoice.
    In some cases, also used to cancel Credit Notes
    """
    _inherit = 'account.debit.note'
    
    date = fields.Date(string='Fecha de la nota de débito', required=True)
    reason = fields.Char(string='Motivo')
    journal_id = fields.Many2one(string='Diario', required=True)
    copy_lines = fields.Boolean(string="Copiar líneas")
    
    def _prepare_default_values(self, move) :
        res = super(AccountDebitNote, self)._prepare_default_values(move)
        res.update({'einvoice_journal_id': res['journal_id']})
        return res
