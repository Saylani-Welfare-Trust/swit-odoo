from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'


    first_para_halfnama = fields.Text('First Halfnama')
    second_para_halfnama = fields.Text('Second Halfnama')
    third_para_halfnama = fields.Text('Third Halfnama')