from odoo import models, fields


class InstallationCategory(models.Model):
    _name = 'installation.category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Installation Category"


    name = fields.Char('Name')