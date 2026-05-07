from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ApiQurbaniOrderLine(models.Model):
    _name = 'api.qurbani.order.line'
    _description = "Api Qurbani Order Line"


    qurbani_order_id = fields.Many2one('api.donation', string="Qurbani Order")
    product_id = fields.Many2one('product.product', string="Product")
    # currency_id = fields.Many2one('res.currency', related='qurbani_order_id.currency_id')
    city_id = fields.Many2one('stock.location', string="City")
    distribution_id = fields.Many2one('stock.location', string="Distribution")
    day_id = fields.Many2one('qurbani.day', string="Day")
    hijri_id = fields.Many2one('hijri', string="Hijri")

    name = fields.Char('Name', default="New")
    hissa_name = fields.Char('Hissa Name')

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    quantity = fields.Integer('Quantity', default=1)

    amount = fields.Float('Amount')
