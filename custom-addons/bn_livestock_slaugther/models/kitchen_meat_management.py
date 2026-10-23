from odoo import models, fields


class KitchenMeatManagement(models.Model):
    _name = 'kitchen.meat.management'
    _description = "Kitchen Meat Management"


    meat_management_id = fields.Many2one('meat.management', string="Meat Management")

    date = fields.Date('Date')

    quantity = fields.Float('Quantity')