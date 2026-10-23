from odoo import models, fields, api

class WelfareTeacher(models.Model):
    _name = 'welfare.teacher'
    _description = 'Madrasa Teacher'
    
    welfare_id = fields.Many2one('welfare', string='Welfare Application', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    
    name = fields.Char(string='Name', required=True)
    designation = fields.Char(string='Designation')
    educational_qualification = fields.Char(string='Educational Qualification')
    other_degree_name = fields.Char(string='Other Degree Name')
    cnic = fields.Char(string='CNIC')
    phone = fields.Char(string='Phone')