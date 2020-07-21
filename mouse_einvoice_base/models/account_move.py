# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

from zipfile import ZipFile 
import os
import base64
from io import BytesIO
import requests
from xml.dom.minidom import parse, parseString
import signxml
from lxml import etree
from OpenSSL import crypto

DEFAULT_ZIPCODE = "150101"

class AccountMove(models.Model) :
    _inherit = 'account.move'
    
    @api.model
    def _get_default_einvoice_journal(self) :
        return self._get_default_journal()
    
    unsigned_xml = fields.Text(string='XML sin firmar', copy=False)
    unsigned_xml_binary = fields.Binary(string='XML (sin firma)', help='Representación XML sin firmar del comprobante', copy=False)
    unsigned_xml_binary_filename = fields.Char(string='Nombre del archivo XML (sin firma)', copy=False)
    signed_xml = fields.Text(string='XML firmado', copy=False)
    signed_xml_binary = fields.Binary(string='XML (firmado)', help='Representación XML firmada del comprobante', copy=False)
    signed_xml_binary_filename = fields.Char(string='Nombre del archivo XML (firmado)', copy=False)
    signed_xml_digest_value = fields.Text(string='DSig digest value', help='Digest value of the XML digital signature', copy=False)
    digest_value = fields.Text(string='SUNAT digest value', help='Digest value of the SUNAT answer', copy=False)
    sunat_answer = fields.Char(string='Respuesta de la SUNAT', help='Respuesta recibida de la SUNAT', copy=False)
    cod_sunat = fields.Char(string='Código de respuesta de la SUNAT', help='Código de respuesta recibido de la SUNAT', copy=False)
    sent_sunat = fields.Boolean(string='Enviado a la SUNAT', copy=False)
    sent_sunat_beta = fields.Boolean(string='Enviado al servidor de pruebas de la SUNAT', copy=False)
    einvoice_journal_id = fields.Many2one('account.journal', string='Comprobante', required=True, readonly=True, states={'draft': [('readonly', False)]}, domain="[('company_id', '=', company_id)]", default=_get_default_einvoice_journal, store=True)
    
    l10n_latam_document_type_id = fields.Many2one(string='Tipo de documento', related='journal_id.l10n_latam_document_type_id', store=True, auto_join=False, copy=False)
    l10n_latam_document_type_credit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Tipo de nota de crédito', related='journal_id.l10n_latam_document_type_credit_id', readonly=False, store=True, copy=False)
    l10n_latam_document_type_debit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Tipo de nota de débito', related='journal_id.l10n_latam_document_type_debit_id', readonly=False, store=True, copy=False)
    
    credit_origin_id = fields.Many2one(comodel_name='account.move', string='Comprobante rectificado', readonly=True, copy=False)
    credit_note_ids = fields.One2many(comodel_name='account.move', inverse_name='credit_origin_id', string='Notas de crédito', help="Las notas de crédito creadas para este comprobante")
    credit_note_count = fields.Integer(string='Número de notas de crédito', compute='_compute_credit_count')
    
    debit_origin_id = fields.Many2one(string='Comprobante debitado')
    
    @api.depends('credit_note_ids')
    def _compute_credit_count(self) :
        credit_data = self.env['account.move'].read_group([('credit_origin_id', 'in', self.ids)], ['credit_origin_id'], ['credit_origin_id'])
        data_map = {datum['credit_origin_id'][0]: datum['credit_origin_id_count'] for datum in credit_data}
        for inv in self:
            inv.credit_note_count = data_map.get(inv.id, 0)
    
    def action_view_credit_notes(self) :
        self.ensure_one()
        tipo = self.type.split('_')[0] + '_refund'
        action = self.env.ref('account.action_move_' + tipo + '_type').read()[0]
        if self.credit_note_count > 1 :
            action['domain'] = [('credit_origin_id','in',self.ids)]
        else :
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            action['views'] = form_view + [(state, view) for state, view in action.get('views', [('form', 'form')]) if view != 'form']
            action['res_id'] = self.credit_note_ids.id
        return action
    
    def action_view_debit_notes(self) :
        action = super(AccountMove, self).action_view_debit_notes()
        action = self.env.ref('account.action_move_' + self.type + '_type').read()[0]
        if self.debit_note_count > 1 :
            action['domain'] = [('debit_origin_id','in',self.ids)]
        else :
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            action['views'] = form_view + [(state, view) for state, view in action.get('views', [('form', 'form')]) if view != 'form']
            action['res_id'] = self.debit_note_ids.id
        return action
    
    @api.depends('l10n_latam_available_document_type_ids')
    @api.depends_context('internal_type')
    def _compute_l10n_latam_document_type(self) :
        #Getting rid of the evil method that overwrites the document type
        super(models.Model, self)
    
    def _get_sequence_prefix(self) :
        """ If we use documents we update sequences only from journal """
        if self.env.ref('base.pe', False) in (self.company_id.country_id or self.env.company.country_id) :
            return super(models.Model, self)._get_sequence_prefix()
        else :
            return super(AccountMove, self)._get_sequence_prefix()
    
    @api.onchange('l10n_latam_document_type_id', 'l10n_latam_document_number')
    def _inverse_l10n_latam_document_number(self) :
        super(AccountMove, self)._inverse_l10n_latam_document_number()
        for rec in self.filtered('l10n_latam_document_type_id').filtered(lambda r: r.l10n_latam_document_number and r.company_id.country_id == self.env.ref('base.pe', False)) :
            l10n_latam_document_number = len(str(rec.l10n_latam_document_type_id.doc_code_prefix)) + 1 #Support of False prefix
            l10n_latam_document_number = rec.name[l10n_latam_document_number:]
            if rec.journal_id.l10n_latam_document_type_id.code == '07' :
                rec.name = rec.journal_id.l10n_latam_document_type_credit_id.doc_code_prefix + l10n_latam_document_number
            elif rec.journal_id.l10n_latam_document_type_id.code == '08' :
                rec.name = rec.journal_id.l10n_latam_document_type_debit_id.doc_code_prefix + l10n_latam_document_number
            else :
                rec.name = rec.journal_id.l10n_latam_document_type_id.doc_code_prefix + l10n_latam_document_number
    
    def _get_document_type_sequence(self) :
        """ Method to be inherited by different localizations. """
        self.ensure_one()
        if self.env.ref('base.pe', False) in self.company_id.country_id :
            return self.journal_id.sequence_id
        else :
            return super(AccountMove, self)._get_document_type_sequence()
    
    @api.onchange('einvoice_journal_id')
    def onchange_einvoice_journal_id(self) :
        self.journal_id = self.einvoice_journal_id
        self.l10n_latam_document_type_id = self.einvoice_journal_id.l10n_latam_document_type_id
    
    @api.model
    def create(self, vals) :
        if vals.get('journal_id', False) :
            if not vals.get('einvoice_journal_id', False) :
                vals['einvoice_journal_id'] = vals['journal_id']
        else :
            if vals.get('einvoice_journal_id', False) :
                vals['journal_id'] = vals['einvoice_journal_id']
        
        current_journal = vals.get('journal_id', False) and self.env['account.journal'].browse(vals['journal_id'])
        
        if current_journal :
            if not vals.get('l10n_latam_document_type_id', False) or vals['l10n_latam_document_type_id'] != current_journal.l10n_latam_document_type_id.id :
                vals['l10n_latam_document_type_id'] = current_journal.l10n_latam_document_type_id.id
            if current_journal.l10n_latam_document_type_id.code == '07' :
                if not vals.get('l10n_latam_document_type_credit_id', False) or vals['l10n_latam_document_type_credit_id'] != current_journal.l10n_latam_document_type_credit_id.id :
                    vals['l10n_latam_document_type_credit_id'] = current_journal.l10n_latam_document_type_credit_id.id
            elif current_journal.l10n_latam_document_type_id.code == '08' :
                if not vals.get('l10n_latam_document_type_debit_id', False) or vals['l10n_latam_document_type_debit_id'] != current_journal.l10n_latam_document_type_debit_id.id :
                    vals['l10n_latam_document_type_debit_id'] = current_journal.l10n_latam_document_type_debit_id.id
        
        return super(AccountMove, self).create(vals)
    
    def write(self, values) :
        if values.get('journal_id', False) :
            if not values.get('einvoice_journal_id', False) :
                values['einvoice_journal_id'] = values['journal_id']
        else :
            if values.get('einvoice_journal_id', False) :
                values['journal_id'] = values['einvoice_journal_id']
        
        if values.get('journal_id', False) :
            current_journal = values.get('journal_id', False) and self.env['account.journal'].browse(values['journal_id'])
            
            if current_journal :
                if not values.get('l10n_latam_document_type_id', False) or values['l10n_latam_document_type_id'] != current_journal.l10n_latam_document_type_id.id :
                    values['l10n_latam_document_type_id'] = current_journal.l10n_latam_document_type_id.id
                if current_journal.l10n_latam_document_type_id.code == '07' :
                    if not values.get('l10n_latam_document_type_credit_id', False) or values['l10n_latam_document_type_credit_id'] != current_journal.l10n_latam_document_type_credit_id.id :
                        values['l10n_latam_document_type_credit_id'] = current_journal.l10n_latam_document_type_credit_id.id
                elif current_journal.l10n_latam_document_type_id.code == '08' :
                    if not values.get('l10n_latam_document_type_debit_id', False) or values['l10n_latam_document_type_debit_id'] != current_journal.l10n_latam_document_type_debit_id.id :
                        values['l10n_latam_document_type_debit_id'] = current_journal.l10n_latam_document_type_debit_id.id
        
        return super(AccountMove, self).write(values)
    
    def cifras_a_letras(self, numero, hay_mas) :
        lista_centena = ["",("CIEN","CIENTO"),"DOSCIENTOS","TRESCIENTOS","CUATROCIENTOS","QUINIENTOS","SEISCIENTOS","SETECIENTOS","OCHOCIENTOS","NOVECIENTOS"]
        lista_decena = ["",("DIEZ","ONCE","DOCE","TRECE","CATORCE","QUINCE","DIECISEIS","DIECISIETE","DIECIOCHO","DIECINUEVE"),
                        ("VEINTE","VEINTI"),("TREINTA","TREINTA Y"),("CUARENTA", "CUARENTA Y"),("CINCUENTA","CINCUENTA Y"),
                        ("SESENTA","SESENTA Y"),("SETENTA","SETENTA Y"),("OCHENTA","OCHENTA Y"),("NOVENTA","NOVENTA Y")]
        lista_unidad = ["",("UN","UNO"),"DOS","TRES","CUATRO","CINCO","SEIS","SIETE","OCHO","NUEVE"]
        centena = int(numero / 100)
        decena = int((numero % 100) / 10)
        unidad = int(numero % 10)
        
        texto_centena = lista_centena[centena]
        if centena == 1 :
            texto_centena = texto_centena[int((decena+unidad)>0)]
        
        texto_decena = lista_decena[decena]
        if decena == 1 :
            texto_decena = texto_decena[unidad]
        elif decena > 1 :
            texto_decena = texto_decena[int(unidad>0)]
        
        texto_unidad = lista_unidad[unidad]
        if unidad == 1 :
            texto_unidad = texto_unidad[int(hay_mas)]
        if decena == 1 :
            texto_unidad = ""
        
        if decena > 0 :
            texto_centena = texto_centena + (texto_centena and " "+texto_decena or texto_decena)
        texto_centena = texto_centena + (texto_centena and " "+texto_unidad or texto_unidad)
        return texto_centena
    
    def monto_a_letras(self, numero) :
        #asume no negativo con hasta dos decimales
        indicador = [("",""),("MIL","MIL"),("MILLON","MILLONES"),("MIL","MIL"),("BILLON","BILLONES")]
        entero = int(numero)
        decimal = int((numero * 100) % 100)
        
        contador = 0
        numero_letras = ""
        
        while entero > 0 :
            millar = entero % 1000
            
            en_letras = self.cifras_a_letras(millar,(contador==0)).strip()
            
            #if millar == 0 :
            #    numero_letras = en_letras + (numero_letras and " "+numero_letras or "")
            #elif millar == 1 :
            #    if contador %2 == 1 :
            #        numero_letras = indicador[contador][0] + (numero_letras and " "+numero_letras or "")
            #    else :
            #        numero_letras = en_letras + " " + indicador[contador][0] + (numero_letras and " "+numero_letras or "")
            #else :
            #    numero_letras = en_letras + " " + indicador[contador][1] + (numero_letras and " "+numero_letras or "")
            numero_letras = ((millar == 1 and contador %2 == 1) and "" or (en_letras and (en_letras + " ") or "")) + (millar == 0 and "" or indicador[contador][int(millar != 1)]) + (numero_letras and (" " + numero_letras) or "")
            
            contador = contador + 1
            entero = entero // 1000
        
        if numero_letras == "" :
            numero_letras = "CERO"
        
        numero_letras = numero_letras + " CON " + str(decimal).rjust(2,"0") + "/100"
        return numero_letras
    
    def crear_xml_factura(self) :
        xml_doc = '''<?xml version="1.0" encoding="utf-8"?>
<Invoice
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ccts="urn:un:unece:uncefact:documentation:2"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
    xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID schemeAgencyName="PE:SUNAT">2.0</cbc:CustomizationID>
    <cbc:ProfileID
        schemeName="Tipo de Operacion"
        schemeAgencyName="PE:SUNAT"
        schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo51">'''
        xml_doc = xml_doc + '''0101'''
        xml_doc = xml_doc + '''</cbc:ProfileID>
    <cbc:ID>'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:ID>
    <cbc:IssueDate>'''
        xml_doc = xml_doc + str(self.invoice_date)
        xml_doc = xml_doc + '''</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:DueDate>'''
        xml_doc = xml_doc + str(self.invoice_date_due)
        xml_doc = xml_doc + '''</cbc:DueDate>
    <cbc:InvoiceTypeCode
        listAgencyName="PE:SUNAT"
        listName="Tipo de Documento"
        listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01"
        listID="0101"
        name="Tipo de Operacion"
        listSchemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo51">'''
        xml_doc = xml_doc + self.journal_id.l10n_latam_document_type_id.code #('''01''' if len(invoice.partner_id.vat) == 11 else '''03''')
        xml_doc = xml_doc + '''</cbc:InvoiceTypeCode>
    <cbc:Note
        languageLocaleID="1000">'''
        xml_doc = xml_doc + self.monto_a_letras(self.amount_total)
        xml_doc = xml_doc + '''</cbc:Note>
    <cbc:DocumentCurrencyCode
        listID="ISO 4217 Alpha"
        listName="Currency"
        listAgencyName="United Nations Economic Commission for Europe">'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''</cbc:DocumentCurrencyCode>
    <cbc:LineCountNumeric>'''
        xml_doc = xml_doc + str(len(self.invoice_line_ids))
        xml_doc = xml_doc + '''</cbc:LineCountNumeric>'''
    
    #    if ('''$cabecera["NRO_OTR_COMPROBANTE"]''' != "") :
    #        xml_doc = xml_doc + '''
    #<cac:OrderReference>
    #    <cbc:ID>''' + '''$cabecera["NRO_OTR_COMPROBANTE"]''' + '''</cbc:ID>
    #</cac:OrderReference>'''
    
    #    if ('''$cabecera["NRO_GUIA_REMISION"]''' != "") :
    #        xml_doc = xml_doc + '''
    #<cac:DespatchDocumentReference>
    #    <cbc:ID>''' + '''$cabecera["NRO_GUIA_REMISION"]''' + '''</cbc:ID>
    #    <cbc:IssueDate>''' + '''$cabecera["FECHA_GUIA_REMISION"]''' + '''</cbc:IssueDate>
    #    <cbc:DocumentTypeCode
    #        listAgencyName="PE:SUNAT"
    #        listName="Tipo de Documento"
    #        listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01">''' + '''$cabecera["COD_GUIA_REMISION"]''' + '''</cbc:DocumentTypeCode>
    #</cac:DespatchDocumentReference>'''
    
        xml_doc = xml_doc + '''
    <cac:Signature>
        <cbc:ID>'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>'''
        
        company_partner = self.company_id.partner_id
        if not company_partner.l10n_latam_identification_type_id :
            raise UserError(_("Debe configurar el tipo de documento de identidad de la compañía del usuario."))
        elif company_partner.l10n_latam_identification_type_id.l10n_pe_vat_code != '6' :
            raise UserError(_("La compañía del usuario debe tener RUC."))
        elif (not company_partner.vat) or len(company_partner.vat.strip()) != 11 :
            raise UserError(_("El RUC de la compañía del usuario solo debe tener 11 caracteres."))
        if not self.partner_id.check_vat_pe(company_partner.vat.strip()) :
            raise UserError(_("El RUC de la compañía del usuario no es válido."))
        
        xml_doc = xml_doc + company_partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>'''
        xml_doc = xml_doc + (company_partner.registration_name or company_partner.name)
        xml_doc = xml_doc + '''</cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        xml_doc = xml_doc + company_partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + company_partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + (company_partner.commercial_name or "")
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
            <cac:PartyTaxScheme>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + (company_partner.registration_name or company_partner.name)
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cbc:CompanyID
                    schemeID="'''
        xml_doc = xml_doc + company_partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + company_partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:CompanyID>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="'''
        xml_doc = xml_doc + company_partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                        schemeName="SUNAT:Identificador de Documento de Identidad"
                        schemeAgencyName="PE:SUNAT"
                        schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + company_partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
                </cac:TaxScheme>
            </cac:PartyTaxScheme>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + (company_partner.registration_name or company_partner.name)
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:ID
                        schemeName="Ubigeos"
                        schemeAgencyName="PE:INEI"/>
                    <cbc:AddressTypeCode
                        listAgencyName="PE:SUNAT"
                        listName="Establecimientos anexos">0000</cbc:AddressTypeCode>
                    <cbc:CityName><![CDATA['''
        
        default_district = self.env.ref('l10n_pe.district_pe_'+DEFAULT_ZIPCODE)
        
        if company_partner.country_id.code != 'PE' :
            company_partner.country_id = self.env.ref('base.pe')
        if not company_partner.state_id and not company_partner.city_id and company_partner.l10n_pe_district :
            company_partner.write({'state_id': default_district.city_id.state_id.id,
                                   'city_id': default_district.city_id.id,
                                   'l10n_pe_district': default_district.id,
                                   'zip': default_district.code})
        if not company_partner.state_id :
            company_partner.state_id = default_district.city_id.state_id
        if not company_partner.city_id :
            company_partner.city_id = (company_partner.state_id == default_district.city_id.state_id and default_district.city_id or self.env['res.city'].search([('state_id','=',company_partner.state_id.id)], order='l10n_pe_code asc', limit=1))
        if not company_partner.l10n_pe_district :
            company_partner.l10n_pe_district = (company_partner.city_id == default_district.city_id and default_district or self.env['l10n_pe.res.city.district'].search([('city_id','=',company_partner.city_id.id)], order='code asc', limit=1))
        if company_partner.zip != company_partner.l10n_pe_district.code :
            company_partner.zip = company_partner.l10n_pe_district.code
        
        #if company_partner.l10n_pe_district :
        #    if not company_partner.zip or company_partner.zip != company_partner.l10n_pe_district.code :
        #        company_partner.zip = company_partner.l10n_pe_district.code
        #elif company_partner.city_id :
        #    company_partner.l10n_pe_district = self.env['l10n_pe.res.city.district'].search([('city_id','in',company_partner.city_id.ids)],limit=1)
        #    company_partner.zip = company_partner.l10n_pe_district.code
        #elif company_partner.state_id :
        #    company_partner.city_id = self.env['res.city'].search([('state_id','in',company_partner.state_id.ids)],limit=1)
        #    company_partner.l10n_pe_district = self.env['l10n_pe.res.city.district'].search([('city_id','in',company_partner.city_id.ids)],limit=1)
        #    company_partner.zip = company_partner.l10n_pe_district.code
        #else :
        #    distrito = self.env['l10n_pe.res.city.district'].search([('city_id','!=',False),('code','=',DEFAULT_ZIPCODE)],limit=1)
        #    if not company_partner.country_id :
        #        company_partner.country_id = distrito.city_id.country_id
        #    company_partner.state_id = distrito.city_id.state_id
        #    company_partner.province_id = distrito.city_id
        #    company_partner.l10n_pe_district = distrito
        #    company_partner.zip = distrito.code
        
        xml_doc = xml_doc + company_partner.state_id.name.upper()
        xml_doc = xml_doc + ''']]></cbc:CityName>
                    <cbc:CountrySubentity><![CDATA['''
        xml_doc = xml_doc + company_partner.city_id.name.upper()
        xml_doc = xml_doc + ''']]></cbc:CountrySubentity>
                    <cbc:District><![CDATA['''
        xml_doc = xml_doc + company_partner.l10n_pe_district.name.upper()
        xml_doc = xml_doc + ''']]></cbc:District>
                    <cac:AddressLine>
                        <cbc:Line><![CDATA['''
        
        if not company_partner.street_name :
            company_partner.street_name = "DIRECCION DESCONOCIDA"
        
        xml_doc = xml_doc + company_partner.street_name.upper()
        xml_doc = xml_doc + ''']]></cbc:Line>
                    </cac:AddressLine>
                    <cac:Country>
                        <cbc:IdentificationCode
                            listID="ISO 3166-1"
                            listAgencyName="United Nations Economic Commission for Europe"
                            listName="Country">'''
        xml_doc = xml_doc + company_partner.country_id.code.upper() #get_country_iso_code(invoice.company_id.country_id.id)
        xml_doc = xml_doc + '''</cbc:IdentificationCode>
                    </cac:Country>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        
        partner = self.partner_id
        if not partner.l10n_latam_identification_type_id :
            raise UserError(_("Debe fijar el tipo de documento de identidad del cliente."))
        
        xml_doc = xml_doc + partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        
        if not partner.vat :
            raise UserError(_("Debe fijar el número del documento de identidad del cliente."))
        
        xml_doc = xml_doc + partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + (partner.registration_name or partner.name)
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
            <cac:PartyTaxScheme>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + (partner.registration_name or partner.name)
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cbc:CompanyID
                    schemeID="'''
        xml_doc = xml_doc + partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:CompanyID>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="'''
        xml_doc = xml_doc + partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                        schemeName="SUNAT:Identificador de Documento de Identidad"
                        schemeAgencyName="PE:SUNAT"
                        schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
                </cac:TaxScheme>
            </cac:PartyTaxScheme>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + (partner.registration_name or partner.name)
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:ID
                        schemeName="Ubigeos"
                        schemeAgencyName="PE:INEI">'''
        
        if partner.country_id.code != 'PE' :
            partner.country_id = self.env.ref('base.pe')
        if not partner.state_id and not partner.city_id and partner.l10n_pe_district :
            partner.write({'state_id': default_district.city_id.state_id.id,
                                   'city_id': default_district.city_id.id,
                                   'l10n_pe_district': default_district.id,
                                   'zip': default_district.code})
        if not partner.state_id :
            partner.state_id = default_district.city_id.state_id
        if not partner.city_id :
            partner.city_id = (partner.state_id == default_district.city_id.state_id and default_district.city_id or self.env['res.city'].search([('state_id','=',partner.state_id.id)], order='l10n_pe_code asc', limit=1))
        if not partner.l10n_pe_district :
            partner.l10n_pe_district = (partner.city_id == default_district.city_id and default_district or self.env['l10n_pe.res.city.district'].search([('city_id','=',partner.city_id.id)], order='code asc', limit=1))
        if partner.zip != partner.l10n_pe_district.code :
            partner.zip = partner.l10n_pe_district.code
        
        #if partner.l10n_pe_district :
        #    if not partner.zip or partner.zip != partner.l10n_pe_district.code :
        #        partner.zip = partner.l10n_pe_district.code
        #elif partner.city_id :
        #    partner.l10n_pe_district = self.env['l10n_pe.res.city.district'].search([('city_id','in',partner.city_id.ids)],limit=1)
        #    partner.zip = partner.l10n_pe_district.code
        #elif partner.state_id :
        #    partner.city_id = self.env['res.city'].search([('state_id','in',partner.state_id.ids)],limit=1)
        #    partner.l10n_pe_district = self.env['l10n_pe.res.city.district'].search([('city_id','in',partner.city_id.ids)],limit=1)
        #    partner.zip = partner.l10n_pe_district.code
        #else :
        #    distrito = self.env['l10n_pe.res.city.district'].search([('city_id','!=',False),('code','=',DEFAULT_ZIPCODE)],limit=1)
        #    if not partner.country_id :
        #        partner.country_id = distrito.city_id.country_id
        #    partner.state_id = distrito.city_id.state_id
        #    partner.province_id = distrito.city_id
        #    partner.l10n_pe_district = distrito
        #    partner.zip = distrito.code
        
        xml_doc = xml_doc + partner.zip
        xml_doc = xml_doc + '''</cbc:ID>
                    <cbc:CityName><![CDATA['''
        xml_doc = xml_doc + partner.state_id.name.upper()
        xml_doc = xml_doc + ''']]></cbc:CityName>
                    <cbc:CountrySubentity><![CDATA['''
        xml_doc = xml_doc + partner.city_id.name.upper()
        xml_doc = xml_doc + ''']]></cbc:CountrySubentity>
                    <cbc:District><![CDATA['''
        xml_doc = xml_doc + partner.l10n_pe_district.name.upper()
        xml_doc = xml_doc + ''']]></cbc:District>
                    <cac:AddressLine>
                        <cbc:Line><![CDATA['''
        
        if not partner.street_name :
            partner.street_name = "-"
        
        xml_doc = xml_doc + self.partner_id.street_name.upper()
        xml_doc = xml_doc + ''']]></cbc:Line>
                    </cac:AddressLine>
                    <cac:Country>
                        <cbc:IdentificationCode
                            listID="ISO 3166-1"
                            listAgencyName="United Nations Economic Commission for Europe"
                            listName="Country">'''
        xml_doc = xml_doc + partner.country_id.code.upper() #get_country_iso_code(invoice.partner_id.country_id.id)
        xml_doc = xml_doc + '''</cbc:IdentificationCode>
                    </cac:Country>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:AllowanceCharge>
        <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
        <cbc:AllowanceChargeReasonCode
            listName="Cargo/descuento"
            listAgencyName="PE:SUNAT"
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo53">02</cbc:AllowanceChargeReasonCode>
        <cbc:MultiplierFactorNumeric>0.00</cbc:MultiplierFactorNumeric>
        <cbc:Amount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">0.00</cbc:Amount>
        <cbc:BaseAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">0.00</cbc:BaseAmount>
    </cac:AllowanceCharge>
    <cac:TaxTotal>
        <cbc:TaxAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount
                currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxableAmount>
            <cbc:TaxAmount
                currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxCategory>
                <cbc:ID
                    schemeID="UN/ECE 5305"
                    schemeName="Tax Category Identifier"
                    schemeAgencyName="United Nations Economic Commission for Europe">S</cbc:ID>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="UN/ECE 5153"
                        schemeAgencyID="6">1000</cbc:ID>
                    <cbc:Name>IGV</cbc:Name>
                    <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>'''
        
        #TOTAL=GRAVADA+IGV+EXONERADA
        #NO ENTRA GRATUITA(INAFECTA) NI DESCUENTO
        #SUB_TOTAL=PRECIO(SIN IGV) * CANTIDAD
        
        xml_doc = xml_doc + '''
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + '''</cbc:LineExtensionAmount>
        <cbc:TaxInclusiveAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxInclusiveAmount>
        <cbc:AllowanceTotalAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">''' + '''0.00''' + '''</cbc:AllowanceTotalAmount>
        <cbc:ChargeTotalAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">0.00</cbc:ChargeTotalAmount>
        <cbc:PayableAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + '''</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>'''
        
        for line in self.invoice_line_ids.filtered(lambda r: r.display_type==False) :
            moneda = line.currency_id or self.env.ref('base.PEN')
            xml_doc = xml_doc + '''
    <cac:InvoiceLine>
        <cbc:ID>'''
            xml_doc = xml_doc + str(line.id)
            xml_doc = xml_doc + '''</cbc:ID>
        <cbc:InvoicedQuantity
            unitCode="'''
            xml_doc = xml_doc + ('uom_id' in line._fields and line.uom_id.unece_code or line.product_id.uom_id.unece_code or 'NIU')
            xml_doc = xml_doc + '''"
            unitCodeListID="UN/ECE rec 20"
            unitCodeListAgencyName="United Nations Economic Commission for Europe">'''
            xml_doc = xml_doc + format(line.quantity, '.2f')
            xml_doc = xml_doc + '''</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount
            currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
                <cbc:PriceTypeCode
                    listName="Tipo de Precio"
                    listAgencyName="PE:SUNAT"
                    listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo16">'''
            xml_doc = xml_doc + '''01'''
            xml_doc = xml_doc  + '''</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>
            <cbc:TaxAmount
                currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_total - line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxableAmount>
                <cbc:TaxAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_total - line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:ID
                        schemeID="UN/ECE 5305"
                        schemeName="Tax Category Identifier"
                        schemeAgencyName="United Nations Economic Commission for Europe">'''
            xml_doc = xml_doc + line.tax_ids[0].l10n_pe_edi_unece_category #'''S'''
            xml_doc = xml_doc + '''</cbc:ID>
                    <cbc:Percent>'''
            xml_doc = xml_doc + str(int(line.tax_ids[0].amount + 0.5)) #'''18'''
            xml_doc = xml_doc + '''</cbc:Percent>
                    <cbc:TaxExemptionReasonCode
                        listAgencyName="PE:SUNAT"
                        listName="SUNAT:Codigo de Tipo de Afectación del IGV"
                        listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07">'''
            xml_doc = xml_doc + '''10'''
            xml_doc = xml_doc + '''</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID
                            schemeID="UN/ECE 5153"
                            schemeName="Tax Scheme Identifier"
                            schemeAgencyName="United Nations Economic Commission for Europe">'''
            xml_doc = xml_doc + line.tax_ids[0].l10n_pe_edi_tax_code #'''1000'''
            xml_doc = xml_doc + '''</cbc:ID>
                        <cbc:Name>'''
            unece_5153 = dict(line.tax_ids._fields['l10n_pe_edi_tax_code'].selection)[line.tax_ids[0].l10n_pe_edi_tax_code].split(' ')
            xml_doc = xml_doc + unece_5153[0] #'''IGV'''
            xml_doc = xml_doc + '''</cbc:Name>
                        <cbc:TaxTypeCode>'''
            xml_doc = xml_doc + unece_5153[2] #'''VAT'''
            xml_doc = xml_doc + '''</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Description><![CDATA['''
            xml_doc = xml_doc + (line.product_id.name and line.product_id.name.strip() or "GENERIC")
            xml_doc = xml_doc + ''']]></cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID><![CDATA['''
            xml_doc = xml_doc + (line.product_id.default_code and line.product_id.default_code.strip() or "G000")
            xml_doc = xml_doc + ''']]></cbc:ID>
            </cac:SellersItemIdentification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount
                currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
        </cac:Price>
    </cac:InvoiceLine>'''
        
        xml_doc = xml_doc + '''
</Invoice>'''
        
        #with open(ruta+".XML", "wb") as f :
        #    f.write(xml_doc.encode("utf-8"))
        resp = {'respuesta': 'ok', 'unsigned_xml': xml_doc}
        return resp
    
    def crear_xml_nota_credito(self) :
        xml_doc = '''<?xml version="1.0" encoding="utf-8"?>
<CreditNote
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ccts="urn:un:unece:uncefact:documentation:2"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
    xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"
    xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>2.0</cbc:CustomizationID>
    <cbc:ID>'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:ID>
    <cbc:IssueDate>'''
        xml_doc = xml_doc + str(self.invoice_date)
        xml_doc = xml_doc + '''</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:DocumentCurrencyCode>'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''</cbc:DocumentCurrencyCode>
    <cac:DiscrepancyResponse>
        <cbc:ReferenceID>'''
        xml_doc = xml_doc + self.credit_origin_id.name
        xml_doc = xml_doc + '''</cbc:ReferenceID>
        <cbc:ResponseCode>'''
        xml_doc = xml_doc + '''10'''
        xml_doc = xml_doc + '''</cbc:ResponseCode>
        <cbc:Description><![CDATA['''
        xml_doc = xml_doc + (self.ref or "Nota de crédito de "+self.credit_origin_id.name)
        xml_doc = xml_doc + ''']]></cbc:Description>
    </cac:DiscrepancyResponse>
    <cac:BillingReference>
        <cac:InvoiceDocumentReference>
            <cbc:ID>'''
        xml_doc = xml_doc + self.credit_origin_id.name
        xml_doc = xml_doc + '''</cbc:ID>
            <cbc:DocumentTypeCode>'''
        xml_doc = xml_doc + self.credit_origin_id.journal_id.l10n_latam_document_type_id.code
        xml_doc = xml_doc + '''</cbc:DocumentTypeCode>
        </cac:InvoiceDocumentReference>
    </cac:BillingReference>
    <cac:Signature>
        <cbc:ID>IDSignST</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>'''
        
        company_partner = self.company_id.partner_id
        if not company_partner.l10n_latam_identification_type_id :
            raise UserError(_("Debe configurar el tipo de documento de identidad de la compañía del usuario."))
        elif company_partner.l10n_latam_identification_type_id.l10n_pe_vat_code != '6' :
            raise UserError(_("La compañía del usuario debe tener RUC."))
        elif (not company_partner.vat) or len(company_partner.vat.strip()) != 11 :
            raise UserError(_("El RUC de la compañía del usuario solo debe tener 11 caracteres."))
        if not self.partner_id.check_vat_pe(company_partner.vat.strip()) :
            raise UserError(_("El RUC de la compañía del usuario no es válido."))
        
        xml_doc = xml_doc + company_partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + company_partner.name
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#SignatureSP</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        xml_doc = xml_doc + company_partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + company_partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + (company_partner.commercial_name or "")
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + (company_partner.registration_name or company_partner.name)
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:AddressTypeCode>0001</cbc:AddressTypeCode>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        
        partner = self.partner_id
        if not partner.l10n_latam_identification_type_id :
            raise UserError(_("Debe fijar el tipo de documento de identidad del cliente."))
        
        xml_doc = xml_doc + partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        
        if not partner.vat :
            raise UserError(_("Debe fijar el número del documento de identidad del cliente."))
        
        xml_doc = xml_doc + partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + partner.name
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:TaxTotal>
        <cbc:TaxAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount
                currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxableAmount>
            <cbc:TaxAmount
                currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxCategory>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="UN/ECE 5153"
                        schemeAgencyID="6">1000</cbc:ID>
                    <cbc:Name>IGV</cbc:Name>
                    <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:PayableAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + '''</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>'''
        
        for line in self.invoice_line_ids.filtered(lambda r: r.display_type==False) :
            moneda = line.currency_id or self.env.ref('base.PEN')
            xml_doc = xml_doc + '''
    <cac:CreditNoteLine>
        <cbc:ID>'''
            xml_doc = xml_doc + str(line.id)
            xml_doc = xml_doc + '''</cbc:ID>
        <cbc:CreditedQuantity
            unitCode="'''
            xml_doc = xml_doc + ('uom_id' in line._fields and line.uom_id.unece_code or line.product_id.uom_id.unece_code or 'NIU')
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.quantity, '.2f')
            xml_doc = xml_doc + '''</cbc:CreditedQuantity>
        <cbc:LineExtensionAmount
            currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
                <cbc:PriceTypeCode>'''
            xml_doc = xml_doc + '''01'''
            xml_doc = xml_doc + '''</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>
            <cbc:TaxAmount
                currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_total - line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxableAmount>
                <cbc:TaxAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_total - line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:Percent>'''
            xml_doc = xml_doc + str(int(line.tax_ids[0].amount + 0.5)) #'''18'''
            xml_doc = xml_doc + '''</cbc:Percent>
                    <cbc:TaxExemptionReasonCode>'''
            xml_doc = xml_doc + '''10''' #line.igv_type.code
            xml_doc = xml_doc + '''</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID>'''
            xml_doc = xml_doc + line.tax_ids[0].l10n_pe_edi_tax_code #'''1000'''
            xml_doc = xml_doc + '''</cbc:ID>
                        <cbc:Name>'''
            unece_5153 = dict(line.tax_ids._fields['l10n_pe_edi_tax_code'].selection)[line.tax_ids[0].l10n_pe_edi_tax_code].split(' ')
            xml_doc = xml_doc + unece_5153[0] #'''IGV'''
            xml_doc = xml_doc + '''</cbc:Name>
                        <cbc:TaxTypeCode>'''
            xml_doc = xml_doc + unece_5153[2] #'''VAT'''
            xml_doc = xml_doc + '''</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Description><![CDATA['''
            xml_doc = xml_doc + (line.product_id.name and line.product_id.name.strip() or "GENERIC")
            xml_doc = xml_doc + ''']]></cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID><![CDATA['''
            xml_doc = xml_doc + (line.product_id.default_code and line.product_id.default_code.strip() or "G000")
            xml_doc = xml_doc + ''']]></cbc:ID>
            </cac:SellersItemIdentification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount
                currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
        </cac:Price>
    </cac:CreditNoteLine>'''
        
        xml_doc = xml_doc + '''
</CreditNote>'''
        
        #with open(ruta+".XML", "wb") as f :
        #    f.write(xml_doc.encode("utf-8"))
        resp = {'respuesta': 'ok', 'unsigned_xml': xml_doc}
        return resp
    
    def crear_xml_nota_debito(self) :
        xml_doc = '''<?xml version="1.0" encoding="UTF-8"?>
<DebitNote
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ccts="urn:un:unece:uncefact:documentation:2"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
    xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"
    xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>2.0</cbc:CustomizationID>
    <cbc:ID>'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:ID>
    <cbc:IssueDate>'''
        xml_doc = xml_doc + str(self.invoice_date)
        xml_doc = xml_doc + '''</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:DocumentCurrencyCode>'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''</cbc:DocumentCurrencyCode>
    <cac:DiscrepancyResponse>
        <cbc:ReferenceID>'''
        xml_doc = xml_doc + self.debit_origin_id.name
        xml_doc = xml_doc + '''</cbc:ReferenceID>
        <cbc:ResponseCode>'''
        xml_doc = xml_doc + '''02'''
        xml_doc = xml_doc + '''</cbc:ResponseCode>
        <cbc:Description><![CDATA['''
        xml_doc = xml_doc + (self.ref or "Nota de débito a " + self.debit_origin_id.name)
        xml_doc = xml_doc + ''']]></cbc:Description>
    </cac:DiscrepancyResponse>
    <cac:BillingReference>
        <cac:InvoiceDocumentReference>
            <cbc:ID>'''
        xml_doc = xml_doc + self.debit_origin_id.name
        xml_doc = xml_doc + '''</cbc:ID>
            <cbc:DocumentTypeCode>'''
        xml_doc = xml_doc + self.debit_origin_id.journal_id.l10n_latam_document_type_id.code #self.debit_note_type.code
        xml_doc = xml_doc + '''</cbc:DocumentTypeCode>
        </cac:InvoiceDocumentReference>
    </cac:BillingReference>
    <cac:Signature>
        <cbc:ID>IDSignST</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>'''
        
        company_partner = self.company_id.partner_id
        if not company_partner.l10n_latam_identification_type_id :
            raise UserError(_("Debe configurar el tipo de documento de identidad de la compañía del usuario."))
        elif company_partner.l10n_latam_identification_type_id.l10n_pe_vat_code != '6' :
            raise UserError(_("La compañía del usuario debe tener RUC."))
        elif (not company_partner.vat) or len(company_partner.vat.strip()) != 11 :
            raise UserError(_("El RUC de la compañía del usuario solo debe tener 11 caracteres."))
        if not self.partner_id.check_vat_pe(company_partner.vat.strip()) :
            raise UserError(_("El RUC de la compañía del usuario no es válido."))
        
        xml_doc = xml_doc + company_partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + company_partner.name
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#SignatureSP</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        xml_doc = xml_doc + company_partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + company_partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + (company_partner.commercial_name or "")
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + (company_partner.registration_name or company_partner.name)
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:AddressTypeCode>0001</cbc:AddressTypeCode>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        
        partner = self.partner_id
        if not partner.l10n_latam_identification_type_id :
            raise UserError(_("Debe fijar el tipo de documento de identidad del cliente."))
        
        xml_doc = xml_doc + partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        
        if not partner.vat :
            raise UserError(_("Debe fijar el número del documento de identidad del cliente."))
        
        xml_doc = xml_doc + partner.vat.strip()
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + (partner.registration_name or partner.name)
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:TaxTotal>
        <cbc:TaxAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount
                currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxableAmount>
            <cbc:TaxAmount
                currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxCategory>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="UN/ECE 5153"
                        schemeAgencyID="6">1000</cbc:ID>
                    <cbc:Name>IGV</cbc:Name>
                    <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:RequestedMonetaryTotal>
        <cbc:PayableAmount
            currencyID="'''
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + '''</cbc:PayableAmount>
    </cac:RequestedMonetaryTotal>'''
        
        for line in self.invoice_line_ids.filtered(lambda r: r.display_type==False) :
            moneda = line.currency_id or self.env.ref('base.PEN')
            xml_doc = xml_doc + '''
    <cac:DebitNoteLine>
        <cbc:ID>'''
            xml_doc = xml_doc + str(line.id)
            xml_doc = xml_doc + '''</cbc:ID>
        <cbc:DebitedQuantity
            unitCode="'''
            xml_doc = xml_doc + ('uom_id' in line._fields and line.uom_id.unece_code or line.product_id.uom_id.unece_code or 'NIU')
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.quantity, '.2f')
            xml_doc = xml_doc + '''</cbc:DebitedQuantity>
        <cbc:LineExtensionAmount
            currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
                <cbc:PriceTypeCode>'''
            xml_doc = xml_doc + '''01'''
            xml_doc = xml_doc + '''</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>        
            <cbc:TaxAmount
                currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_total - line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxableAmount>
                <cbc:TaxAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_total - line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:Percent>'''
            xml_doc = xml_doc + str(int(line.tax_ids[0].amount + 0.5)) #'''18'''
            xml_doc = xml_doc + '''</cbc:Percent>
                    <cbc:TaxExemptionReasonCode>'''
            xml_doc = xml_doc + '''10''' #line.igv_type.code
            xml_doc = xml_doc + '''</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID>'''
            xml_doc = xml_doc + line.tax_ids[0].l10n_pe_edi_tax_code #'''1000'''
            xml_doc = xml_doc + '''</cbc:ID>
                        <cbc:Name>'''
            unece_5153 = dict(line.tax_ids._fields['l10n_pe_edi_tax_code'].selection)[line.tax_ids[0].l10n_pe_edi_tax_code].split(' ')
            xml_doc = xml_doc + unece_5153[0] #'''IGV'''
            xml_doc = xml_doc + '''</cbc:Name>
                        <cbc:TaxTypeCode>'''
            xml_doc = xml_doc + unece_5153[2] #'''VAT'''
            xml_doc = xml_doc + '''</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        
        <cac:Item>
            <cbc:Description><![CDATA['''
            xml_doc = xml_doc + (line.product_id.name and line.product_id.name.strip() or "GENERIC")
            xml_doc = xml_doc + ''']]></cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID><![CDATA['''
            xml_doc = xml_doc + (line.product_id.default_code and line.product_id.default_code.strip() or "G000")
            xml_doc = xml_doc + ''']]></cbc:ID>
            </cac:SellersItemIdentification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount
                currencyID="'''
            xml_doc = xml_doc + moneda.name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
        </cac:Price>
    </cac:DebitNoteLine>'''
        
        xml_doc = xml_doc + '''
</DebitNote>'''
    
        #with open(ruta+".XML", "wb") as f:
        #    f.write(xml_doc.encode("utf-8"))
        resp = {'respuesta': 'ok', 'unsigned_xml': xml_doc}
        return resp
    
    def signature_xml(self, path, sign_path, sign_pass) :
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
        path = path.encode('utf-8')
        lxml_doc = etree.fromstring(path, parser=parser)
        
        signer = signxml.XMLSigner(method=signxml.methods.enveloped, signature_algorithm="rsa-sha1", digest_algorithm="sha1", c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        
        sign_path_b64 = base64.b64decode(sign_path)
        if sign_path == base64.b64encode(sign_path_b64) :
            sign_path = sign_path_b64[:]
        
        try :
            sign_pkcs12 = crypto.load_pkcs12(sign_path, sign_pass)
        except crypto.SSLError as e :
            raise UserError(_("El archivo del certificado digital presenta errores.\n" + str(e.message)))
        
        sign_cert = sign_pkcs12.get_certificate()
        sign_cert_cryptography = crypto.dump_certificate(crypto.FILETYPE_PEM, sign_cert).decode()
        #sign_cert_cryptography = sign_cert_cryptography.replace("-----END CERTIFICATE-----","").replace("-----BEGIN CERTIFICATE-----", "").replace("\n","")
        #sign_cert  s_cryptography = [sign_cert]
        
        sign_privatekey = sign_pkcs12.get_privatekey()
        sign_privatekey_cryptography = sign_privatekey.to_cryptography_key()
        
        signed_xml = signer.sign(lxml_doc, key=sign_privatekey_cryptography, cert=sign_cert_cryptography, passphrase=sign_pass)
        
        signed_string = etree.tostring(signed_xml).decode()
        ze = signed_string.find("<ds:Sign")
        ko = signed_string.rfind("</ds:Sign") + len("</ds:Signature>")
        signature_string = signed_string[ze:ko].replace("\n", "")
        
        doc = path.decode('utf-8') #etree.tostring(lxml_doc).decode()
        chu = doc.find("</ext:ExtensionContent>")
        xml_doc = doc[:chu] + signature_string + doc[chu:]
        if "xml version" not in xml_doc :
            xml_doc = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" + xml_doc
        
        ze = signature_string.find("<ds:DigestValue>")
        chu = len("<ds:DigestValue>")
        ko = signature_string.find("</ds:DigestValue>")
        digest_value = signature_string[ze+chu:ko]
        
        resp= {'respuesta': 'ok', 'hash_cpe': digest_value, 'signed_xml': xml_doc}
        
        return resp
    
    def enviar_documento(self, ruc, user_sol, pass_sol, file, filepath, path_ws) :
        zip_buffer = BytesIO()
        
        soapURL = path_ws
        
        soapUser = user_sol
        soapPass = pass_sol
        xml_doc = '''<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
    xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ser="http://service.sunat.gob.pe" 
    xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
    <soapenv:Header>
        <wsse:Security>
            <wsse:UsernameToken>
                <wsse:Username>'''
        xml_doc = xml_doc + ruc + soapUser
        xml_doc = xml_doc + '''</wsse:Username>
                <wsse:Password>'''
        xml_doc = xml_doc + soapPass
        xml_doc = xml_doc + '''</wsse:Password>
            </wsse:UsernameToken>
        </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
        <ser:sendBill>
            <fileName>'''
        xml_doc = xml_doc + filepath
        xml_doc = xml_doc + '''.zip</fileName>
            <contentFile>'''
        
        with ZipFile(zip_buffer, "a") as zip_file:
            zip_file.writestr(filepath+".XML", file.encode())
        
        zip_buffer.seek(0)
        xml_doc = xml_doc + base64.b64encode(zip_buffer.read()).decode("latin-1")
        
        xml_doc = xml_doc + '''</contentFile>
        </ser:sendBill>
    </soapenv:Body>
</soapenv:Envelope>'''
        
        headers = {"Content-type": '''text/xml;charset="utf-8"''',
                    "Accept": "text/xml",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "SOAPAction": "",
                    "Content-length": str(len(xml_doc))}
        
        resp_code = requests.post(soapURL, data=xml_doc, headers=headers)
        content = parseString(resp_code.text)
        
        if len(content.getElementsByTagNameNS("*", "applicationResponse")) > 0 :
            content = content.getElementsByTagNameNS("*", "applicationResponse")[0].childNodes[0].nodeValue.strip()
            
            with ZipFile(BytesIO(base64.b64decode(content))) as thezip :
                for zipinfo in thezip.infolist() :
                    with thezip.open(zipinfo) as thefile:
                        respuesta_xml = thefile.read().decode()
            
            #Hash CDR
            content = parseString(respuesta_xml)
            mensaje = {"cod_sunat": content.getElementsByTagNameNS("*", "ResponseCode")[0].childNodes[0].nodeValue,
                        "msj_sunat": content.getElementsByTagNameNS("*", "Description")[0].childNodes[0].nodeValue,
                        "hash_cdr": content.getElementsByTagNameNS("*", "DigestValue")[0].childNodes[0].nodeValue}
        else :
            mensaje = {"cod_sunat": content.getElementsByTagNameNS("*", "faultcode")[0].childNodes[0].nodeValue,
                        "msj_sunat": content.getElementsByTagNameNS("*", "faultstring")[0].childNodes[0].nodeValue,
                        "hash_cdr": ""}
        
        return mensaje
    
    def action_sign_xml(self) :
        for record in self :
            invoice_company = record.company_id
            sign_path = invoice_company._default_digital_certificate()
            sign_pass = '123456'
            if (not invoice_company.beta_service) and (invoice_company.user_sol != "MODDATOS" or invoice_company.pass_sol != "MODDATOS") :
                sign_path = invoice_company.digital_certificate
                sign_pass = invoice_company.digital_password
            signed_invoice_dictionary = record.signature_xml(record.unsigned_xml, sign_path, sign_pass)
            record.write({'signed_xml': signed_invoice_dictionary['signed_xml'],
                          'signed_xml_binary': base64.b64encode(signed_invoice_dictionary['signed_xml'].encode()),
                          #'signed_xml_binary_filename': invoice_company.partner_id.vat + '-' + record.journal_id.l10n_latam_document_type_id.code + '-' + record.name + (invoice_company.beta_service and ' - BETA' or '') + '.xml',
                          'signed_xml_binary_filename': record.unsigned_xml_binary_filename[:-4] + (invoice_company.beta_service and ' - BETA' or '') + record.unsigned_xml_binary_filename[-4:],
                          'signed_xml_digest_value': signed_invoice_dictionary['hash_cpe']})
    
    def action_create_xml(self) :
        for record in self :
            invoice_company = record.company_id
            unsigned_invoice_dictionary = {}
            tipo_veri = record.journal_id.l10n_latam_document_type_id.code
            if tipo_veri in ['01', '03'] :
                unsigned_invoice_dictionary = record.crear_xml_factura()
            elif tipo_veri == '07' :
                unsigned_invoice_dictionary = record.crear_xml_nota_credito()
            elif tipo_veri == '08' :
                unsigned_invoice_dictionary = record.crear_xml_nota_debito()
            
            if unsigned_invoice_dictionary :
                nombre = invoice_company.partner_id.vat + '-' + tipo_veri + '-' + record.name
                record.write({'unsigned_xml': unsigned_invoice_dictionary['unsigned_xml'],
                              'unsigned_xml_binary': base64.b64encode(unsigned_invoice_dictionary['unsigned_xml'].encode()),
                              'unsigned_xml_binary_filename': nombre + '.xml'})
    
    def action_post(self) :
        res = super(AccountMove, self).action_post()
        for record in self.filtered(lambda r: r.company_id.country_id == self.env.ref('base.pe', False)) :
            tipo_veri = record.journal_id.l10n_latam_document_type_id.code
            if tipo_veri == '07' :
                tipo_veri = record.journal_id.l10n_latam_document_type_credit_id.code
            elif tipo_veri == '08' :
                tipo_veri = record.journal_id.l10n_latam_document_type_debit_id.code
            
            if tipo_veri == '01' and ((not record.partner_id.l10n_latam_identification_type_id) or record.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code != '6' or not record.partner_id.vat or len(record.partner_id.vat) != 11) :
                #Factura con DNI
                if len(self) == 1 :
                    raise UserError(_("No puede validar una factura con un cliente que no posea RUC."))
                else :
                    raise UserError(_("No se pudieron validar las facturas porque el cliente de la factura " + record.name + " no posee RUC."))
            if tipo_veri == '03' :
                if not record.partner_id.l10n_latam_identification_type_id :
                    record.partner_id.l10n_latam_identification_type_id = self.env.ref('l10n_pe.it_DNI')
                if not record.partner_id.vat :
                    record.partner_id.vat = '11111111'
            
            record.action_create_xml()
        return res
    
    def action_send_sunat(self) :
        if self.filtered(lambda r:r.state in ['draft','cancel']) :
            if len(self) == 1 :
                raise UserError(_("Solo puede enviar a la SUNAT un comprobante validado."))
            else :
                raise UserError(_("Todos los comprobantes a enviar a la SUNAT deben estar validados.\nPor favor seleccione solo comprobantes validados."))
        
        for record in self.filtered(lambda r: r.company_id.country_id == self.env.ref('base.pe', False)) :
            if not record.signed_xml :
                if not record.unsigned_xml :
                    record.action_create_xml()
                    self.env.cr.commit()
                record.action_sign_xml()
                self.env.cr.commit()
            invoice_company = record.company_id
            user_sol = 'MODDATOS'
            pass_sol = 'MODDATOS'
            path_ws = "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService"
            if invoice_company.beta_service :
                if record.signed_xml_binary_filename[-11:-4] != ' - BETA' :
                    record.action_sign_xml()
                    self.env.cr.commit()
            else :
                if record.signed_xml_binary_filename[-11:-4] == ' - BETA' :
                    record.action_sign_xml()
                    self.env.cr.commit()
                user_sol = invoice_company.user_sol
                pass_sol = invoice_company.pass_sol
                if user_sol != "MODDATOS" and pass_sol != "MODDATOS" :
                    path_ws = "https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService?wsdl"
            
            ruc = invoice_company.partner_id.vat
            filepath = record.unsigned_xml_binary_filename[:-4]
            #filepath = ruc + "-" + record.journal_id.l10n_latam_document_type_id.code + "-" + record.name
            respuesta = record.enviar_documento(ruc, user_sol, pass_sol, record.signed_xml, filepath, path_ws)
            if respuesta['cod_sunat'] == '0' :
                filepath = {'sunat_answer': respuesta['msj_sunat'],
                            'digest_value': respuesta['hash_cdr'],
                            'cod_sunat' : respuesta['cod_sunat']}
                if path_ws == "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService" :
                    filepath.update({'sent_sunat_beta': True})
                else :
                    filepath.update({'sent_sunat': True})
                record.write(filepath)
            else :
                filepath = {'sunat_answer': respuesta['cod_sunat'] + " - " + respuesta['msj_sunat'],
                            'cod_sunat' : respuesta['cod_sunat']}
                if path_ws != "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService" :
                    filepath.update({'sent_sunat': False})
                record.write(filepath)
            self.env.cr.commit()
        
        return True
