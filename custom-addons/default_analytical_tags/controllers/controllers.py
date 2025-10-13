# -*- coding: utf-8 -*-
# from odoo import http


# class DefaultAnalyticalTags(http.Controller):
#     @http.route('/default_analytical_tags/default_analytical_tags', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/default_analytical_tags/default_analytical_tags/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('default_analytical_tags.listing', {
#             'root': '/default_analytical_tags/default_analytical_tags',
#             'objects': http.request.env['default_analytical_tags.default_analytical_tags'].search([]),
#         })

#     @http.route('/default_analytical_tags/default_analytical_tags/objects/<model("default_analytical_tags.default_analytical_tags"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('default_analytical_tags.object', {
#             'object': obj
#         })

