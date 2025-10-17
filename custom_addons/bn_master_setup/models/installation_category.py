from odoo import models, fields


class InstallationCategory(models.Model):
    _name = 'installation.category'
    _description = "Installation Category"


    name = fields.Char('Name')