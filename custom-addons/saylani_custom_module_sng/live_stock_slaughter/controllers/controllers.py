# -*- coding: utf-8 -*-
# from odoo import http


# class LiveStockSlaughter(http.Controller):
#     @http.route('/live_stock_slaughter/live_stock_slaughter', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/live_stock_slaughter/live_stock_slaughter/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('live_stock_slaughter.listing', {
#             'root': '/live_stock_slaughter/live_stock_slaughter',
#             'objects': http.request.env['live_stock_slaughter.live_stock_slaughter'].search([]),
#         })

#     @http.route('/live_stock_slaughter/live_stock_slaughter/objects/<model("live_stock_slaughter.live_stock_slaughter"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('live_stock_slaughter.object', {
#             'object': obj
#         })

