from odoo import fields, models, _

class ShariahLawPerson(models.Model):
    _name = 'shariah.law.person'
    _description = 'Shariah Law Person'
    

    name = fields.Char(string='Name', required=True)