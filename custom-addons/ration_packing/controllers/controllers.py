# -*- coding: utf-8 -*-
# from odoo import http


# class RationPacking(http.Controller):
#     @http.route('/ration_packing/ration_packing', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ration_packing/ration_packing/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('ration_packing.listing', {
#             'root': '/ration_packing/ration_packing',
#             'objects': http.request.env['ration_packing.ration_packing'].search([]),
#         })

#     @http.route('/ration_packing/ration_packing/objects/<model("ration_packing.ration_packing"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ration_packing.object', {
#             'object': obj
#         })

