# -*- coding: utf-8 -*-
# from odoo import http


# class SaylaniGenSerial(http.Controller):
#     @http.route('/saylani_gen_serial/saylani_gen_serial', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/saylani_gen_serial/saylani_gen_serial/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('saylani_gen_serial.listing', {
#             'root': '/saylani_gen_serial/saylani_gen_serial',
#             'objects': http.request.env['saylani_gen_serial.saylani_gen_serial'].search([]),
#         })

#     @http.route('/saylani_gen_serial/saylani_gen_serial/objects/<model("saylani_gen_serial.saylani_gen_serial"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('saylani_gen_serial.object', {
#             'object': obj
#         })

