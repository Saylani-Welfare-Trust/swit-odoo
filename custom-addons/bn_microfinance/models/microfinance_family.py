from odoo import models, fields


class MicrofinanceFamily(models.Model):
    _name = 'microfinance.family'
    _description = "Microfinance Family"


    relation = fields.Char('Relation')
    education = fields.Char('Education')
    complete_name = fields.Char('Complete Name')
    monthly_income = fields.Char('Monthly Income')
    
    age = fields.Integer('Age')

    cnic_b_form = fields.Binary('CNIC / B Form')
    cnic_b_form_name = fields.Char('CNIC / B Form Name')

    microfinance_id = fields.Many2one('microfinance', string="Microfinance")