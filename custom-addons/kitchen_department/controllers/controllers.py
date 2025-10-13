# -*- coding: utf-8 -*-
# from odoo import http


# class KitchenDepartment(http.Controller):
#     @http.route('/kitchen_department/kitchen_department', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/kitchen_department/kitchen_department/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('kitchen_department.listing', {
#             'root': '/kitchen_department/kitchen_department',
#             'objects': http.request.env['kitchen_department.kitchen_department'].search([]),
#         })

#     @http.route('/kitchen_department/kitchen_department/objects/<model("kitchen_department.kitchen_department"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('kitchen_department.object', {
#             'object': obj
#         })

