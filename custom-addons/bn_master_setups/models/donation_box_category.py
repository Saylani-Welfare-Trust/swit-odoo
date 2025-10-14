from odoo import fields, models, _, api, exceptions


class DonationBoxCategory(models.Model):
    _name = 'donation.box.category'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Donation Box Categroy"


    name = fields.Char('Name', tracking=True)