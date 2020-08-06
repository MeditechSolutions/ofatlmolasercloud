# -*- coding: utf-8 -*-

{
    'name': 'Agenda',
    'version': '13.0.1.0.0',
    'author': 'MSTECH',
    'category': 'Technical Configuration',
    'license': 'AGPL-3',
    'website': 'https://www.mstech.pe',
    'depends': [
        'product',
        'base',
        'hr',
    ],
    'data': [
        'data/ir_cron.xml',
        'security/ir.model.access.csv',
        'views/planner_views.xml',
    ],
    'installable': True,
    'sequence': 1,
}
