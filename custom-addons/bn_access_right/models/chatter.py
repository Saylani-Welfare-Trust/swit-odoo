from odoo import api, fields, models

class ResGroups(models.Model):
    _inherit = 'res.groups'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Optional: Add computed fields to show user info
    user_count = fields.Integer(
        string="User Count",
        compute='_compute_user_info',
        store=False,
    )
    
    user_names = fields.Char(
        string="User Names",
        compute='_compute_user_info',
        store=False,
    )
    
    @api.depends('res_users.groups_id')
    def _compute_user_info(self):
        for group in self:
            users = self.env['res.users'].search([('groups_id', 'in', group.id)])
            group.user_count = len(users)
            group.user_names = ', '.join(users.mapped('display_name')) if users else 'No users'