from odoo import models, fields


class MadarisMeatManagement(models.Model):
    _name = 'madaris.meat.management'
    _description = "Madaris Meat Management"


    meat_management_id = fields.Many2one('meat.management', string="Meat Management")

    date = fields.Date('Date')

    quantity = fields.Float('Quantity')