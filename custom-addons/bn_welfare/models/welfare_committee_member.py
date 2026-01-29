from odoo import models, fields, api

class WelfareCommitteeMember(models.Model):
    _name = 'welfare.committee.member'
    _description = 'Committee Member'
    
    welfare_id = fields.Many2one('welfare', string='Welfare Application', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    
    name = fields.Char(string='Name', required=True)
    designation = fields.Char(string='Designation')
    educational_qualification = fields.Char(string='Educational Qualification')
    cnic = fields.Char(string='CNIC')
    phone = fields.Char(string='Phone')