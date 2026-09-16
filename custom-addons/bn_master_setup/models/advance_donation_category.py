from odoo import models, fields


class AdvanceDonationCategory(models.Model):
    _name = 'advance.donation.category'
    _description = "Advance Donation Category"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)
    
    category_lines = fields.One2many('advance.donation.category.line', 'category_id')