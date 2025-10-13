# -*- coding: utf-8 -*-
# from odoo import http


# class DonationBoxSp(http.Controller):
#     @http.route('/donation_box_sp/donation_box_sp', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/donation_box_sp/donation_box_sp/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('donation_box_sp.listing', {
#             'root': '/donation_box_sp/donation_box_sp',
#             'objects': http.request.env['donation_box_sp.donation_box_sp'].search([]),
#         })

#     @http.route('/donation_box_sp/donation_box_sp/objects/<model("donation_box_sp.donation_box_sp"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('donation_box_sp.object', {
#             'object': obj
#         })

