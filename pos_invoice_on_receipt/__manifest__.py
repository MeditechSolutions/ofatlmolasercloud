# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
  "name"                 :  "POS Invoice On Receipt",
  "summary"              :  """Allows POS user to print the invoice on POS Order Receipt. User doesn't need
                            to worry about the invoice as this module prints the invoice on PosTicket. User can also get
                            the invoice on XmlReceipt as well by using this module.""",
  "category"             :  "Point Of Sale",
  "version"              :  "1.0",
  "sequence"             :  1,
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "website"              :  "https://store.webkul.com",
  "description"          :  """Invoice on receipt, invoice on pos ticket, invoice on XmlReceipt, invoice on xmlticket, invoice on ticket,
                            Invoice number on receipt, invoice number on pos ticket, invoice number on XmlReceipt, invoice number on xmlticket, invoice number on ticket,
                            invoice in receipt, invoice in xmlticket, invoice in posreceipt, invoice in pos receipt, invoice receipt, receipt invoice,
                            invoice pos receipt, invoice pos ticket, invoice ticket, invoice xmlticket, invoice xml receipt, invoice xml ticket,
                            invoice xmlreceipt""",
  "live_test_url"        :  "http://odoodemo.webkul.com/?module=pos_invoice_on_receipt&version=13.0&custom_url=/pos/web/#action=pos.ui",
  "depends"              :  ['point_of_sale'],
  "data"                 :  ['views/template.xml'],
  "demo"                 :  ['data/pos_invoice_on_receipt_demo.xml'],
  "qweb"                 :  ['static/src/xml/wk_invoice_on_receipt.xml'],
  "images"               :  ['static/description/banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
  "price"                :  25,
  "currency"             :  "EUR",
  "pre_init_hook"        :  "pre_init_check",
}