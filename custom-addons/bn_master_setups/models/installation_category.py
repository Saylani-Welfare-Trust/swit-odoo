from odoo import fields, models, _, api, exceptions


class InstallationCategory(models.Model):
    _name = 'installation.category'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Donation Box Categroy"


    name = fields.Char('Name', tracking=True)