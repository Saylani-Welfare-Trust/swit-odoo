from odoo import models, fields


class MedicalMeatManagement(models.Model):
    _name = 'medical.meat.management'
    _description = "Medical Meat Management"


    meat_management_id = fields.Many2one('meat.management', string="Meat Management")

    date = fields.Date('Date')

    quantity = fields.Float('Quantity')