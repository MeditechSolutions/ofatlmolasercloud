# -*- coding: utf-8 -*-

{
    'name' : 'Oftalmolaser - Odoo',
    'version' : '13.0.1.0.0',
    'author' : 'Mouse Technologies',
    'category' : 'Accounting & Finance',
    'summary': 'Módulo de personalización para Oftalmolaser.',
    'license': 'LGPL-3',
    'description' : """
Este módulo permite realizar los requisitos solicitados por la empresa Oftalmolaser en Odoo
""",
    'website': 'https://www.mouse.pe',
    'depends' : [
        'mouse_einvoice_base',
        'point_of_sale',
    ],
    'data': [
        'views/mouse_oftalmolaser.xml',
    ],
    'qweb': [
        'static/src/xml/pos.xml',
    ],
    'installable': True,
    'auto_install': False,
    'sequence': 1,
}
