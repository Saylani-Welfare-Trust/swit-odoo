from odoo import fields, models

class ShariahLawPerson(models.Model):
    _name = 'shariah.law.person'
    _description = 'Shariah Law Person'
    

    name = fields.Char(string='Name', required=True)