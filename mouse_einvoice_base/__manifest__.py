# -*- coding: utf-8 -*-

{
    'name': 'Factura electrónica - Base',
    'version': '13.0.1.0.0',
    'author': 'Mouse Technologies',
    'category': 'Accounting & Finance',
    'summary': 'Tablas y requisitos para la factura electrónica.',
    'license': 'LGPL-3',
    'description' : """
Factura electronica - Base.
====================================

Tablas:
--------------------------------------------
    * Tablas requeridas por la Factura electrónica
    """,
    'website': 'https://www.mstech.pe',
    'depends': ['l10n_pe','l10n_latam_invoice_document','account_debit_note','uom_unece'],
    'external_dependencies ': {'python': ['pyOpenSSL','signxml']},
    'data': [
        'security/ir.model.access.csv',
        'data/einvoice_data.xml',
        'data/l10n_latam.document.type.csv',
        'views/ir_sequence_views.xml',
        'views/res_company_views.xml',
        'views/einvoice_views.xml',
        'views/account_views.xml',
        'views/account_move_views.xml',
        'wizard/account_move_reversal_views.xml',
        'wizard/account_debit_note_views.xml',
    ],
    'installable': True,
    'sequence': 1,
}
