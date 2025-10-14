# -*- coding: utf-8 -*-
# from odoo import http


# class ExpenseReport(http.Controller):
#     @http.route('/expense_report/expense_report', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/expense_report/expense_report/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('expense_report.listing', {
#             'root': '/expense_report/expense_report',
#             'objects': http.request.env['expense_report.expense_report'].search([]),
#         })

#     @http.route('/expense_report/expense_report/objects/<model("expense_report.expense_report"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('expense_report.object', {
#             'object': obj
#         })

