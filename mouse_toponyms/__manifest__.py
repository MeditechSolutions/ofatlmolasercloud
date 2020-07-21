# -*- coding: utf-8 -*-

{
    'name': 'Topónimos de Perú',
    'version': '1.0.0',
    'author': 'Mouse Technologies',
    'category': 'Localization/America',
    'summary': 'Vista de topónimos del Perú',
    'license': 'AGPL-3',
    'description' : """
Localizacion Peruana.
====================================

Clientes y Proveedores:
--------------------------------------------
    * Vistas de departamentos, provincias y distritos de todo el Perú
    
    """,
    'website': 'https://www.mstech.pe',
    'depends': ['l10n_pe'],
    'data': [
        'views/res_city_views.xml',
        'views/res_city_district_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'data/l10n_pe.res.city.district.csv',
    ],
    'installable': True,
    'sequence': 1,
}
