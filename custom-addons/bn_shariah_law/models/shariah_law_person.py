from odoo import fields, models

class ShariahLawPerson(models.Model):
    _name = 'shariah.law.person'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Shariah Law Person'
    

    name = fields.Char(string='Name', required=True)