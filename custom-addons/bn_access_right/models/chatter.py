from odoo import api, fields, models

class ResGroups(models.Model):
    _inherit = 'res.groups'
    
    user_count = fields.Integer(
        string="User Count",
        compute='_compute_user_info',
        store=True,  # Must be stored for tracking to work
        tracking=True  # Track changes
    )
    
    user_names = fields.Char(
        string="User Names",
        compute='_compute_user_info',
        store=True,  # Must be stored for tracking to work
        tracking=True  # Track changes
    )
    
    @api.depends('users')
    def _compute_user_info(self):
        for group in self:
            users = group.users
            group.user_count = len(users)
            group.user_names = ', '.join(users.mapped('display_name')) if users else 'No users'