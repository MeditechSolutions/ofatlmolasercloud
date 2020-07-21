# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning
import requests

DEFAULT_ZIPCODE = "150101"

def get_data_ruc(numero_doc):
    url = 'https://api.sunat.cloud/ruc'
    url = '%s/%s' % (url, str(numero_doc))
    res = {'error': True, 'message': None, 'data': {}}
    try:
        response = requests.get(url, timeout=10)
    except:
        res['message'] = 'Error en la conexion'
        return res
    
    if response.status_code == 200:
        res['error'] = False
        res['data'] = response.json()
    else:
        try:
            res['message'] = response.json()
        except Exception as e:
            res['error'] = True
    return res

def get_data_doc_number(tipo_doc, numero_doc, format='json'):
    user, password = 'demorest', 'demo1234'
    url = 'http://py-devs.com/api'
    url = '%s/%s/%s' % (url, tipo_doc, str(numero_doc))
    res = {'error': True, 'message': None, 'data': {}}
    try:
        response = requests.get(url, auth=(user, password), timeout=10)
    except:
        res['message'] = 'Error en la conexion'
        return res
    
    if response.status_code == 200:
        res['error'] = False
        res['data'] = response.json()
    else:
        try:
            res['message'] = response.json()['detail']
        except Exception as e:
            res['error'] = True
    return res

def new_get_data_doc_number(tipo_doc, numero_doc, format='json'):
    user, password = 'Hf526gujsgerd12', 'Hf526gujsgerd12'
    url = 'https://sistemadefacturacionelectronicasunat.com/api'
    url = '%s/%s/%s/%s' % (url, tipo_doc, str(numero_doc), password)
    res = {'error': True, 'message': None, 'data': {}}
    try:
        response = requests.get(url, timeout=10)
    except:
        res['message'] = 'Error en la conexion'
        return res
    
    if response.status_code == 200:
        res['error'] = False
        data = response.json()
        if len(numero_doc) == 8 :
            if not (data['nombres'] or data['ap_paterno'] or data['ap_materno']) :
                data['nombre'] = "".join(e for e in data['nombre'] if e.isalpha() or e in [" ","-","_"] or e.isdigit())
                nombres = data['nombre'].rsplit(" ",2)
                data['nombres'] = nombres[0]
                data['ape_paterno'] = nombres[1]
                data['ape_materno'] = nombres[2]
        else :
            data['provincia'] = 'LIMA'
            data['distrito'] = 'LIMA'
            data['condicion_contribuyente'] = data['condicion']
            data['nombre'] = data['razon_social']
            data['domicilio_fiscal'] = data['direccion']
        res['data'] = data
    else:
        try:
            res['message'] = response.json()['respuesta']
        except Exception as e:
            res['error'] = True
    return res

class Partner(models.Model):
    _inherit = 'res.partner'
    
    commercial_name = fields.Char(string="Nombre comercial", index=True)
    registration_name = fields.Char(string="Razón social", index=True)
    l10n_latam_identification_type_id = fields.Many2one(string="Tipo Doc. Id.")
    vat = fields.Char(string="Nro. Doc. Id.")
    state = fields.Selection(string="State", selection=[('habido','Habido'),('nhabido','No Habido')])
    
    @api.onchange('name')
    def _cambio_nombre_razon_social(self) :
        self.registration_name = self.name
    
    #@api.depends('is_company', 'name', 'parent_id.name', 'type', 'company_name', 'commercial_name')
    #def _compute_display_name(self) :
    #    super(Partner, self)._compute_display_name()
    #    for partner in self :
    #        partner.display_name = (partner.vat + " - " if partner.vat else "") + partner.display_name + (" - " + partner.commercial_name if partner.commercial_name else "")
    
    def _get_name(self):
        nombre = super(Partner, self)._get_name()
        #if not self._context.get('show_vat') or not self.vat :
        #    nombre = nombre + (self.vat + " ‒ " if self.vat else "")
        return nombre
    
    def name_get(self) :
        res = super(Partner, self).name_get()
        #new_res = res[:]
        #for old_name in res :
        #    new_res.remove(old_name)
        #    new_name = list(old_name)
        #    if isinstance(new_name[0], int) and self.search([('id','=',new_name[0])]) :
        #        new_name.append(self.browse(new_name[0]).vat)
        #        if new_name[2] and (' ‒ ' + new_name[2]) not in new_name[1] :
        #            new_name[1] = new_name[1] + ' ‒ ' + new_name[2] #not the common hyphen
        #        new_name = new_name[:2]
        #    new_res.append(tuple(new_name))
        #return new_res
        return res
    
    @api.onchange('l10n_latam_identification_type_id','vat')
    def vat_change(self) :
        if self.l10n_latam_identification_type_id.l10n_pe_vat_code in ['1','6'] and self.vat and self.vat.strip() :
            self.update_document()
    
    def update_document(self) :
        if len(self) != 1 or not self.l10n_latam_identification_type_id or not self.vat or not self.vat.strip() :
            return False
        cif = self.vat.strip()
        district_id_default = self.env.ref("l10n_pe.district_pe_" + DEFAULT_ZIPCODE)
        if self.l10n_latam_identification_type_id.l10n_pe_vat_code == '1' :
            if len(cif) != 8 or not cif.isdigit() :
                cif = 'El DNI' + (len(cif) != 8 and ' debe tener 8 caracteres' or '')+ ((len(cif) != 8 and not cif.isdigit()) and ' y ' or '') + ((not cif.isdigit()) and ' solo debe poseer caracteres numéricos' or '')
                raise Warning(cif)
            
            d = get_data_doc_number("dni", cif, format="json")
            #d = new_get_data_doc_number("persona", cif, format="json")
            if d['error'] :
                return True
            d = d['data']
            
            self.name = '%s %s %s' % (d['nombres'], d['ape_paterno'], d['ape_materno'])
            self.street_name = False
            self.country_id = district_id_default.city_id.country_id
            self.state_id = district_id_default.city_id.state_id
            self.city_id = district_id_default.city_id
            self.l10n_pe_district = district_id_default
            self.zip = district_id_default.code
        elif self.l10n_latam_identification_type_id.l10n_pe_vat_code == '6' :
            if len(cif) != 11 or not cif.isdigit() :
                cif = 'El RUC' + (len(cif) != 11 and ' debe tener 11 caracteres' or '') + ((len(cif) != 11 and not cif.isdigit()) and ' y' or '') + ((not cif.isdigit()) and ' solo debe poseer caracteres numéricos' or '')
                raise Warning(cif)
            if not self.check_vat_pe(cif) :
                raise Warning('El RUC ingresado no es válido')
            
            d = get_data_ruc(cif)
            #d = get_data_doc_number('ruc', cif, format='json')
            #d = new_get_data_doc_number('empresa', cif, format='json')
            if d['error'] :
                return True
            d = d['data']
            
            city_ids = self.env['res.city']
            if 'provincia' in d and d['provincia'] :
                if d['provincia'].strip().upper() != district_id_default.city_id.name.upper() :
                    city_ids = city_ids.search([('country_id','=',173),('name','ilike',d['provincia'].strip())])
                else :
                    city_ids = district_id_default.city_id
            if city_ids :
                if 'distrito' in d and d['distrito'] :
                    if d['distrito'].strip().upper() != district_id_default.name.upper() :
                        district_id_default = self.env['l10n_pe.res.city.district'].search([('city_id','in',city_ids.ids),('name','ilike',d['distrito'].strip())],limit=1) or district_id_default
            
            self.country_id = district_id_default.city_id.country_id
            self.state_id = district_id_default.city_id.state_id
            self.city_id = district_id_default.city_id
            self.l10n_pe_district = district_id_default
            self.zip = district_id_default.code
            
            ##d = get_data_doc_number('ruc', cif, format='json')
            #self.name = d['nombre'].strip()
            ##self.registration_name = d['nombre'] #related field
            #self.commercial_name = d['nombre_comercial'].strip() or d['nombre'].strip()
            #self.street_name = d['domicilio_fiscal'].strip()
            #self.state = d['condicion_contribuyente'].strip() == 'HABIDO' and 'habido' or 'nhabido'
            #self.is_company = True
            
            ##d = get_data_ruc(cif)
            self.name = d['razon_social'].strip()
            #self.registration_name = d['razon_social'] #related field
            self.commercial_name = d['nombre_comercial'].strip() != '-' and d['nombre_comercial'].strip()
            self.street_name = d['domicilio_fiscal'].strip()
            self.state = d['contribuyente_condicion'].strip().upper() == 'HABIDO' and 'habido' or 'nhabido'
            self.is_company = True
            
            return True
        return True
