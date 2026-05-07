from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ApiQurbaniOrderLine(models.Model):
    _name = 'api.qurbani.order.line'
    _description = "Api Qurbani Order Line"


    api_donation_id = fields.Many2one('api.donation', string='Donation Data')
    product_id = fields.Many2one('product.product', string="Product")
    currency = fields.Char(string="Currency", related='api_donation_id.currency')
    city_id = fields.Many2one('stock.location', string="City")
    distribution_id = fields.Many2one('stock.location', string="Distribution")
    day_id = fields.Many2one('qurbani.day', string="Day")
    hijri_id = fields.Many2one('hijri', string="Hijri")

    name = fields.Char('Name', default="New")
    hissa_name = fields.Char('Hissa Name')

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    quantity = fields.Integer('Quantity', default=1)

    amount = fields.Monetary('Amount')
