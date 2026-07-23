from odoo import api, fields, models

class ResGroups(models.Model):
    _inherit = 'res.groups'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    
    # Add the users field explicitly if it doesn't exist
    users = fields.Many2many(
        'res.users',
        'res_users_groups_rel',
        'gid',
        'uid',
        string='Users'
    )
    
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
    
    # Override write to add chatter messages
    def write(self, vals):
        result = super(ResGroups, self).write(vals)
        # If users were modified, post to chatter
        if 'users' in vals:
            for record in self:
                record.message_post(
                    body=f"<b>Users updated</b><br/>Current users: {record.user_names}",
                    subject="User Update Notification"
                )
        return result