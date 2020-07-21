# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, Warning
import qrcode
from io import BytesIO
import base64
from lxml import etree

class AccountMove(models.Model) :
    _inherit = 'account.move'
    
    def _create_qr(self, ver, box, bor, data) :
        qr = qrcode.QRCode(version=ver, error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=box, border=bor)
        qr.add_data(data)
        if ver is None :
            qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img
    
    def generate_qr_base_64(self) :
        self.ensure_one()
        partner = self.partner_id.sudo()
        if not partner.country_id :
            partner.country_id = self.env.ref('base.pe')
        if not partner.state_id :
            partner.state_id = self.env.ref('base.state_pe_15')
        if not partner.city_id :
            partner.city_id = self.env.ref('l10n_pe.city_pe_1501')
        if not partner.l10n_pe_district :
            partner.l10n_pe_district = self.env.ref('l10n_pe.district_pe_150101')
        if not self.unsigned_xml :
            self.action_create_xml()
        self.action_sign_xml()
        listado = [self.company_id.partner_id.vat or '', self.journal_id.l10n_latam_document_type_id.code or ''] + self.name.split('-')
        listado = listado + [format(self.amount_tax or 0, '.2f'), format(self.amount_total or 0, '.2f'), self.invoice_date.strftime('%Y-%m-%d')]
        listado = listado + [self.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code or '', self.partner_id.vat or '']
        
        #lxml_doc = etree.fromstring(self.signed_xml.encode('utf-8'), parser=etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8'))
        #listado = listado + [lxml_doc.xpath("//ds:DigestValue", namespaces={'ds': 'http://www.w3.org/2000/09/xmldsig#'})[0].text, '']
        listado = listado + [self.signed_xml_digest_value, '']
        
        img = self._create_qr(ver=None, box=4, bor=2, data='|'.join(listado))
        buffered = BytesIO()
        img.save(buffered)
        img_string = base64.b64encode(buffered.getvalue())
        return img_string
    
    def post(self) :
        for record in self.filtered(lambda r: r.company_id.country_id == self.env.ref('base.pe')) :
            if record.pos_order_ids.ids :
                vat = record.partner_id.vat
                if vat and vat != vat.strip() :
                    record.partner_id.vat = vat.strip()
                if not vat :
                    record.partner_id.vat = '11111111'
                if len(record.partner_id.vat) == 11 :
                    record.partner_id.l10n_latam_identification_type_id = self.env.ref('l10n_latam_base.it_vat')
                    diario = self.env['account.journal'].search([('company_id','in',record.company_id.ids),
                                                                 ('type','=','sale'),
                                                                 ('l10n_latam_use_documents','!=',False),
                                                                 ('l10n_latam_document_type_id','=',self.env.ref('mouse_einvoice_base.pe_01').id)], limit=1)
                    if diario :
                        record.einvoice_journal_id = diario
                else :
                    if len(record.partner_id.vat) == 8 :
                        record.partner_id.l10n_latam_identification_type_id = self.env.ref('l10n_pe.it_DNI')
                    else :
                        record.partner_id.l10n_latam_identification_type_id = self.env.ref('l10n_latam_base.it_fid')
                    diario = self.env['account.journal'].search([('company_id','in',record.company_id.ids),
                                                                 ('type','=','sale'),
                                                                 ('l10n_latam_use_documents','!=',False),
                                                                 ('l10n_latam_document_type_id','=',self.env.ref('mouse_einvoice_base.pe_03').id)], limit=1)
                    if diario :
                        record.einvoice_journal_id = diario
        res = super(AccountMove, self).post()
        return res
