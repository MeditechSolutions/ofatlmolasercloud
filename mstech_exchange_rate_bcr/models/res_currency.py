# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

import requests
import datetime

MESES_MONTHS = {'Ene':'Jan',
                'Feb':'Feb',
                'Mar':'Mar',
                'Abr':'Apr',
                'May':'May',
                'Jun':'Jun',
                'Jul':'Jul',
                'Ago':'Aug',
                'Set':'Sep',
                'Oct':'Oct',
                'Nov':'Nov',
                'Dic':'Dec'}
LIMITE_CODIGOS = 10

class CurrencyRate(models.Model) :
    _inherit = 'res.currency.rate'
    
    def _use_bcr_api(self, url_api, lista_codigos_bcr, tipo_salida, fecha_inicio, fecha_fin=False) :
        if not url_api or not lista_codigos_bcr or not tipo_salida or not fecha_inicio :
            return False
        #limitado a 10, se corta
        lista = [url_api, '-'.join(lista_codigos_bcr[:LIMITE_CODIGOS]), tipo_salida]
        if fecha_fin :
            if fecha_fin > fecha_inicio :
                lista.append(f'{fecha_inicio.year}-{fecha_inicio.month}-{fecha_inicio.day}')
                lista.append(f'{fecha_fin.year}-{fecha_fin.month}-{fecha_fin.day}')
            elif fecha_fin == fecha_inicio :
                lista.append(f'{fecha_inicio.year}-{fecha_inicio.month}-{fecha_inicio.day}')
            else :
                lista.append(f'{fecha_fin.year}-{fecha_fin.month}-{fecha_fin.day}')
                lista.append(f'{fecha_inicio.year}-{fecha_inicio.month}-{fecha_inicio.day}')
        else :
            lista.append(f'{fecha_inicio.year}-{fecha_inicio.month}-{fecha_inicio.day}')
        try :
            peticion = requests.get('/'.join(lista))
        except :
            return False
        return peticion
    
    @api.model
    def calcular_tasa_dolar_euro_bcr(self, company_ids=False) :
        #Series diarias: https://estadisticas.bcrp.gob.pe/estadisticas/series/diarias
        #Ayuda: https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api
        url_api = 'https://estadisticas.bcrp.gob.pe/estadisticas/series/api'
        lista_codigos_bcr = []
        #PD04639PD: TC Sistema bancario SBS (S/ por US$) - Compra
        dolar = self.env.ref('base.USD')
        if self.env['res.currency'].sudo().search([('id','=',dolar.id)]) :
            lista_codigos_bcr.append('PD04639PD')
        #PD04647PD: TC Euro (S/ por Euro) - Compra
        euro = self.env.ref('base.EUR')
        if self.env['res.currency'].sudo().search([('id','=',euro.id)]) :
            lista_codigos_bcr.append('PD04647PD')
        compas = company_ids
        if not compas :
            compas = self.env['res.company'].sudo().search([]).filtered(lambda r: r.partner_id.country_id and self.env.ref('base.pe') == r.partner_id.country_id)
        if lista_codigos_bcr and compas :
            serie_PD04639PD = -1
            if 'PD04639PD' in lista_codigos_bcr :
                serie_PD04639PD = lista_codigos_bcr.index('PD04639PD')
            serie_PD04647PD = -1
            if 'PD04647PD' in lista_codigos_bcr :
                serie_PD04647PD = lista_codigos_bcr.index('PD04647PD')
            fecha_fin = datetime.date.today()
            fecha_inicio = fecha_fin - datetime.timedelta(days=7)
            r = self._use_bcr_api(url_api=url_api, lista_codigos_bcr=lista_codigos_bcr, tipo_salida='json', fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
            if r :
                a = r.json()
                tasas = a['periods']
                for valor in tasas :
                    fecha = valor['name'].split('.')
                    fecha[1] = MESES_MONTHS[fecha[1]]
                    fecha = datetime.datetime.strptime('.'.join(fecha), '%d.%b.%y').date()
                    if serie_PD04639PD >= 0 :
                        ratio = valor['values'][serie_PD04639PD]
                        try :
                            ratio = float(ratio)
                        except :
                            ratio = False
                        if ratio :
                            ratio = 1.0 / ratio
                            for compa in (compas - self.env['res.currency.rate'].sudo().search([('name','=',fecha), ('currency_id','=',dolar.id)]).company_id) :
                                self.env['res.currency.rate'].sudo().create({'name': str(fecha), 'currency_id': dolar.id, 'company_id': compa.id, 'rate': ratio})
                    if serie_PD04647PD >= 0 :
                        ratio = valor['values'][serie_PD04647PD]
                        try :
                            ratio = float(ratio)
                        except :
                            ratio = False
                        if ratio :
                            ratio = 1.0 / ratio
                            for compa in (compas - self.env['res.currency.rate'].sudo().search([('name','=',fecha), ('currency_id','=',euro.id)]).company_id) :
                                self.env['res.currency.rate'].sudo().create({'name': str(fecha), 'company_id': compa.id, 'currency_id': euro.id, 'rate': ratio})
