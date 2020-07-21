odoo.define('mouse_oftalmolaser.models', function (require) {
    "use strict";
    
    var pos_model = require("point_of_sale.models");
    var SuperPosModel = pos_model.PosModel.prototype;
    var SuperOrder = pos_model.Order.prototype;
    var rpc = require('web.rpc');
    
    pos_model.PosModel = pos_model.PosModel.extend({
        _flush_orders: function(orders, options) {
            var self = this;
            var result, data;
            result = data = SuperPosModel._flush_orders.call(this, orders, options);
            _.each(orders, function(order) {
                if (order.to_invoice) {
                    data.then(function(order_server_id) {
                        rpc.query({
                            model: 'pos.order',
                            method: 'invoice_data_get',
                            args: [order_server_id],
                        }).then(function(result_dict) {
                            if (result_dict.length) {
                                let invoice = result_dict[0].account_move;
                                self.get_order().invoice_id = invoice[1];
                            }
                        }).catch(function(error) {
                            return result;
                        })
                    });
                }
            });
            return result;
        },
    });
    
    pos_model.Order = pos_model.Order.extend({
        export_for_printing: function() {
            var self = this;
            var receipt = SuperOrder.export_for_printing.call(this);
            if (self.invoice_id || this.invoice_id) {
                var invoice = self.invoice_id;
                if (invoice.qr_code) {
                    invoice['qr_code'] = 'data:image/png;base64,' + invoice.qr_code;
                }
                receipt.invoice_id = invoice;
            }
            return receipt;
        },
    });
});
