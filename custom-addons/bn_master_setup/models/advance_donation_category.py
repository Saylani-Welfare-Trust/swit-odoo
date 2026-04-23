from odoo import models, fields


class AdvanceDonationCategory(models.Model):
    _name = 'advance.donation.category'
    _description = "Advance Donation Category"


    name = fields.Char('Name')
    
    category_lines = fields.One2many('advance.donation.category.line', 'category_id')