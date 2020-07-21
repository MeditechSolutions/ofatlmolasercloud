# -*- coding: utf-8 -*-

from . import models
from odoo import api, SUPERUSER_ID

def l10n_latam_base_view_partner_latam_form_active(cr, registry) :
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('l10n_latam_base.view_partner_latam_form').write({'active': True})
    env.ref('base_vat.view_partner_form').write({'active': True})
