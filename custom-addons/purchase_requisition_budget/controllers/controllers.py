    # -*- coding: utf-8 -*-
# from odoo import http


# class FotcoCustomModule(http.Controller):
#     @http.route('/fotco_custom_module/fotco_custom_module', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/fotco_custom_module/fotco_custom_module/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('fotco_custom_module.listing', {
#             'root': '/fotco_custom_module/fotco_custom_module',
#             'objects': http.request.env['fotco_custom_module.fotco_custom_module'].search([]),
#         })

#     @http.route('/fotco_custom_module/fotco_custom_module/objects/<model("fotco_custom_module.fotco_custom_module"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('fotco_custom_module.object', {
#             'object': obj
#         })
