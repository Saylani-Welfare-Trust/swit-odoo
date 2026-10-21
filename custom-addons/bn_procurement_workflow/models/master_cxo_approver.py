from odoo import models, fields

class MasterCxoApprover(models.Model):
    _name = 'master.cxo.approver'
    _description = 'CXO Approver List'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)