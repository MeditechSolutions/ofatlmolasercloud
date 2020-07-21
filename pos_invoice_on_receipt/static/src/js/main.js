/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */
odoo.define('pos_invoice_on_receipt.pos_invoice_on_receipt',function(require){
    "use strict"
    
    var pos_model = require("point_of_sale.models");
    var SuperPosModel = pos_model.PosModel.prototype;
    var SuperOrder = pos_model.Order.prototype;
    var rpc = require('web.rpc');

    pos_model.PosModel = pos_model.PosModel.extend({

        _flush_orders: function(orders, options) {
            var self = this;
            var result, data
            result = data = SuperPosModel._flush_orders.call(this,orders, options)
            _.each(orders,function(order){
                if (order.to_invoice)
                    data.then(function(order_server_id){
                            rpc.query({
                            model: 'pos.order',
                            method: 'read',
                            args:[order_server_id, ['account_move']]
                                }).then(function(result_dict){
                                    if(result_dict.length){
                                        let invoice = result_dict[0].account_move;
                                        self.get_order().invoice_id = invoice[1]
                                    }
                            })
                            .catch(function(error){
                                return result
                            })
                    })
            })
            return result

        },

    })
    pos_model.Order = pos_model.Order.extend({
        export_for_printing: function(){
            var self = this
            var receipt = SuperOrder.export_for_printing.call(this)
            if(self.invoice_id){
                var invoice_id = self.invoice_id
                var invoice = invoice_id.split("(")[0]
                receipt.invoice_id = invoice
            }
            return receipt
        }
    })


})
