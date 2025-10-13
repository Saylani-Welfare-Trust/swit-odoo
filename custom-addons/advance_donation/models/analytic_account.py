from odoo import models, fields,api
from odoo.exceptions import UserError


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    productline = fields.One2many('analytic.product.line','analytic_id',string='Product Line')

class ProductLine(models.Model):
    _name = 'analytic.product.line'

    analytic_id= fields.Many2one('account.analytic.account',string='Analtyic')
    product_id = fields.Many2one('product.product',string="Product")
    name = fields.Char(string='Name')

    @api.onchange('product_id')
    def onchange_prodcut_id(self):
        
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
           