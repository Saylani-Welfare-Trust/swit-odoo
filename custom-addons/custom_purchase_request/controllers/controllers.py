# -*- coding: utf-8 -*-
# from odoo import http


# class CustomPurchaseRequest(http.Controller):
#     @http.route('/custom_purchase_request/custom_purchase_request', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/custom_purchase_request/custom_purchase_request/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('custom_purchase_request.listing', {
#             'root': '/custom_purchase_request/custom_purchase_request',
#             'objects': http.request.env['custom_purchase_request.custom_purchase_request'].search([]),
#         })

#     @http.route('/custom_purchase_request/custom_purchase_request/objects/<model("custom_purchase_request.custom_purchase_request"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('custom_purchase_request.object', {
#             'object': obj
#         })

