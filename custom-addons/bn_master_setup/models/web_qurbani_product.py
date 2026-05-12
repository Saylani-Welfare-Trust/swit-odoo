from odoo import models, fields, api

class WebQurbaniProduct(models.Model): 
    _name = 'web.qurbani.product' 
    _description = "Web Qurbani Product" 


    name = fields.Char('Name') 
    product_id = fields.Many2one('product.product', string="Product")