# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, Warning
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import datetime
import pytz

DEFAULT_TIMEZONE = 'America/Lima'

class PosConfiguration(models.Model):
    _inherit = 'pos.config'
    
    check = fields.Boolean(string='Import Sale Order', default=False)
    load_orders_days = fields.Integer('Load Orders of Last Days')

class InheritPOSOrder(models.Model):
    _inherit = 'pos.order'
    
    def search_all_sale_order(self,config_id,l_date):
        final_order = []
        last_day = datetime.datetime.strptime(l_date,DEFAULT_SERVER_DATETIME_FORMAT)
        config = self.env['pos.config'].browse(config_id)
        #if config.load_orders_days > 0:
        #    sale_orders = self.env['sale.order'].search([('date_order','>=',last_day)])
        #    domain.append(('date_order','>=',last_day))
        #else:
        #    sale_orders = self.env['sale.order'].search([])
        domain = [('company_id','=',config.company_id.id), ('currency_id','=',config.currency_id.id)]
        if config.load_orders_days > 0 :
            domain.append(('date_order','>=',last_day))
        sale_orders = self.env['sale.order'].sudo().search(domain)
        for s in sale_orders:
            vals1 = {
                'id':s.id,
                'name': s.name,
                'state' : s.state,
                'partner_id' : [s.partner_id.id,s.partner_id.name],
                'user_id':[s.user_id.id,s.user_id.name],
                'amount_untaxed':s.amount_untaxed,
                'order_line':s.order_line.ids,
                'amount_tax':s.amount_tax,
                'amount_total':s.amount_total,
                'company_id':[s.company_id.id,s.company_id.name],
                #'date_order':s.date_order,
                'date_order':s.date_order.astimezone(pytz.timezone(self.env.user.tz or DEFAULT_TIMEZONE)).strftime('%d/%m/%Y, %H:%M:%S'),
            }
            final_order.append(vals1)
        return final_order
    
    def return_new_order_line(self):
        orderlines = self.env['sale.order.line'].search([('order_id.id','=', self.id)])
        final_lines = []
        for l in orderlines:
            vals1 = {
                        'discount': l.discount,
                        'id': l.id,
                        'order_id': [l.order_id.id, l.order_id.name],
                        'price_unit': l.price_unit,
                        'product_id': [l.product_id.id, l.product_id.name],
                        'product_uom_qty': l.product_uom_qty,
                        'price_subtotal' : l.price_subtotal,
                 }
            final_lines.append(vals1)
        return final_lines
    
    def sale_order_line(self):
        orderlines = self.env['sale.order.line'].sudo().search([])
        final_lines = []
        for l in orderlines:
            vals1 = {
                    'discount': l.discount,
                    'id': l.id,
                    'order_id': [l.order_id.id, l.order_id.name],
                    'price_unit': l.price_unit,
                    'product_id': [l.product_id.id, l.product_id.name],
                    'product_uom_qty': l.product_uom_qty,
                    'price_subtotal' : l.price_subtotal,
             }
            final_lines.append(vals1)
        return final_lines
