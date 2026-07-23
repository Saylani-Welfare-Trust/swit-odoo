from odoo import api, fields, models

class ResGroups(models.Model):
    _inherit = 'res.groups'  # This is correct - model names should be lowercase
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    
    # Add the users field explicitly
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
        store=True,
        tracking=True
    )
    
    user_names = fields.Char(
        string="User Names",
        compute='_compute_user_info',
        store=True,
        tracking=True
    )
    
    @api.depends('users')
    def _compute_user_info(self):
        for group in self:
            users = group.users
            group.user_count = len(users)
            group.user_names = ', '.join(users.mapped('display_name')) if users else 'No users'
    
    def write(self, vals):
        result = super(ResGroups, self).write(vals)
        if 'users' in vals:
            for record in self:
                record.message_post(
                    body=f"<b>Users updated</b><br/>Current users: {record.user_names}",
                    subject="User Update Notification"
                )
        return result
    
    def action_open_user_wizard(self):
        """Open wizard to add users to the group"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Users to Group',
            'res_model': 'res.groups.add.users.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_group_id': self.id,
                'default_existing_user_ids': self.users.ids,
            }
        }

# Wizard for adding users
class ResGroupsAddUsersWizard(models.TransientModel):
    _name = 'res.groups.add.users.wizard'  # Model names should be lowercase
    _description = 'Add Users to Group Wizard'
    
    group_id = fields.Many2one('res.groups', string="Group", required=True)
    user_ids = fields.Many2many('res.users', string="Users to Add", required=True)
    existing_user_ids = fields.Many2many('res.users', string="Existing Users", 
                                         compute='_compute_existing_users', store=False)
    
    @api.depends('group_id')
    def _compute_existing_users(self):
        for wizard in self:
            wizard.existing_user_ids = wizard.group_id.users if wizard.group_id else self.env['res.users']
    
    def action_add_users(self):
        """Add selected users to the group"""
        self.ensure_one()
        if self.group_id and self.user_ids:
            # Add users to the group
            current_users = self.group_id.users
            all_users = current_users | self.user_ids
            self.group_id.write({
                'users': [(6, 0, all_users.ids)]
            })
            
            # Post message to chatter
            user_names = ', '.join(self.user_ids.mapped('display_name'))
            self.group_id.message_post(
                body=f"<b>Users added:</b> {user_names}",
                subject="New Users Added"
            )
        
        return {'type': 'ir.actions.act_window_close'}

# Also track changes when users are added/removed from the user side
class ResUsers(models.Model):
    _inherit = 'res.users'
    
    def write(self, vals):
        # Get old groups before the write
        if 'groups_id' in vals:
            old_groups = {user.id: set(user.groups_id.ids) for user in self}
        
        result = super(ResUsers, self).write(vals)
        
        if 'groups_id' in vals:
            for user in self:
                new_group_ids = set(user.groups_id.ids)
                old_group_ids = old_groups.get(user.id, set())
                
                # Groups that were added
                added_groups = new_group_ids - old_group_ids
                if added_groups:
                    groups = self.env['res.groups'].browse(list(added_groups))
                    for group in groups:
                        group.message_post(
                            body=f"<b>User added:</b> {user.display_name}",
                            subject="User Added to Group"
                        )
                        # Recompute the user info
                        group._compute_user_info()
                
                # Groups that were removed
                removed_groups = old_group_ids - new_group_ids
                if removed_groups:
                    groups = self.env['res.groups'].browse(list(removed_groups))
                    for group in groups:
                        group.message_post(
                            body=f"<b>User removed:</b> {user.display_name}",
                            subject="User Removed from Group"
                        )
                        # Recompute the user info
                        group._compute_user_info()
        
        return result