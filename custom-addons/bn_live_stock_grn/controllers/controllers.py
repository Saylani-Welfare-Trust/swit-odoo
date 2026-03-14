# -*- coding: utf-8 -*-
# from odoo import http


# class LiveStockGrn(http.Controller):
#     @http.route('/live_stock_grn/live_stock_grn', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/live_stock_grn/live_stock_grn/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('live_stock_grn.listing', {
#             'root': '/live_stock_grn/live_stock_grn',
#             'objects': http.request.env['live_stock_grn.live_stock_grn'].search([]),
#         })

#     @http.route('/live_stock_grn/live_stock_grn/objects/<model("live_stock_grn.live_stock_grn"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('live_stock_grn.object', {
#             'object': obj
#         })

