from odoo import api, fields, models

class ResGroups(models.Model):
    _inherit = 'res.groups'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Computed fields for user count and names
    user_count = fields.Integer(
        string="Count",
        compute='_compute_user_info',
        store=True,  # Stored for performance
        tracking=True  # Track changes
    )
    
    user_names = fields.Char(
        string="Names",
        compute='_compute_user_info',
        store=True,  # Stored for performance
        tracking=True  # Track changes
    )
    
    @api.depends('res_users.groups_id')  # Correct dependency - watches the inverse relation
    def _compute_user_info(self):
        for group in self:
            # Get users through the inverse relation
            users = self.env['res.users'].search([('groups_id', 'in', group.id)])
            group.user_count = len(users)
            group.user_names = ', '.join(users.mapped('display_name')) if users else 'No users'
    
    def write(self, vals):
        # Track user changes when groups are modified
        if 'users' in vals or 'user_ids' in vals:
            # Get current users before the change
            old_users = self.env['res.users'].search([('groups_id', 'in', self.ids)])
            
        result = super(ResGroups, self).write(vals)
        
        # Post chatter messages for user changes
        if 'users' in vals or 'user_ids' in vals:
            for group in self:
                # Get new users
                new_users = self.env['res.users'].search([('groups_id', 'in', group.id)])
                
                # Find added and removed users
                added_users = new_users - old_users
                removed_users = old_users - new_users
                
                # Get current user who made the change
                current_user = self.env.user
                
                # Post message for added users
                if added_users:
                    user_names = ', '.join(added_users.mapped('display_name'))
                    group.message_post(
                        body=f"<b>Users Added:</b> {user_names}<br/>"
                             f"<b>Added by:</b> {current_user.display_name}<br/>"
                             f"<b>Total Users:</b> {group.user_count}<br/>"
                             f"<b>All Users:</b> {group.user_names}",
                        subject="Users Added to Group",
                        subtype_xmlid='mail.mt_note'
                    )
                
                # Post message for removed users
                if removed_users:
                    user_names = ', '.join(removed_users.mapped('display_name'))
                    group.message_post(
                        body=f"<b>Users Removed:</b> {user_names}<br/>"
                             f"<b>Removed by:</b> {current_user.display_name}<br/>"
                             f"<b>Total Users:</b> {group.user_count}<br/>"
                             f"<b>All Users:</b> {group.user_names}",
                        subject="Users Removed from Group",
                        subtype_xmlid='mail.mt_note'
                    )
        
        return result


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    def write(self, vals):
        # Track if groups are being modified from the user side
        if 'groups_id' in vals:
            # Store old groups before the change
            old_groups = {user.id: set(user.groups_id.ids) for user in self}
        
        result = super(ResUsers, self).write(vals)
        
        if 'groups_id' in vals:
            current_user = self.env.user
            for user in self:
                new_group_ids = set(user.groups_id.ids)
                old_group_ids = old_groups.get(user.id, set())
                
                # Groups added to this user
                added_groups = new_group_ids - old_group_ids
                if added_groups:
                    groups = self.env['res.groups'].browse(list(added_groups))
                    for group in groups:
                        # Recompute user info
                        group._compute_user_info()
                        group.message_post(
                            body=f"<b>User Added:</b> {user.display_name}<br/>"
                                 f"<b>Added by:</b> {current_user.display_name}<br/>"
                                 f"<b>Total Users:</b> {group.user_count}<br/>"
                                 f"<b>All Users:</b> {group.user_names}",
                            subject="User Added to Group",
                            subtype_xmlid='mail.mt_note'
                        )
                
                # Groups removed from this user
                removed_groups = old_group_ids - new_group_ids
                if removed_groups:
                    groups = self.env['res.groups'].browse(list(removed_groups))
                    for group in groups:
                        # Recompute user info
                        group._compute_user_info()
                        group.message_post(
                            body=f"<b>User Removed:</b> {user.display_name}<br/>"
                                 f"<b>Removed by:</b> {current_user.display_name}<br/>"
                                 f"<b>Total Users:</b> {group.user_count}<br/>"
                                 f"<b>All Users:</b> {group.user_names}",
                            subject="User Removed from Group",
                            subtype_xmlid='mail.mt_note'
                        )
        
        return result