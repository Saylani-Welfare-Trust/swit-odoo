# -*- coding: utf-8 -*-
# from odoo import http


# class Jahaiz(http.Controller):
#     @http.route('/jahaiz/jahaiz', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jahaiz/jahaiz/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jahaiz.listing', {
#             'root': '/jahaiz/jahaiz',
#             'objects': http.request.env['jahaiz.jahaiz'].search([]),
#         })

#     @http.route('/jahaiz/jahaiz/objects/<model("jahaiz.jahaiz"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jahaiz.object', {
#             'object': obj
#         })

