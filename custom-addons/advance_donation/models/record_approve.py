from odoo import models, fields,api
from odoo.exceptions import UserError



class RecordApproval(models.Model):
    _name = 'approval.workflow'

    name = fields.Char(string='Name')
    active_approval = fields.Boolean(string="Active")
    
    users = fields.Many2many('res.users',string='Users')