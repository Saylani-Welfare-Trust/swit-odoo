from odoo import api, fields, models

class ResGroups(models.Model):
    _inherit = 'res.groups'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Simple computed fields to show user info
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


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    def write(self, vals):
        # Store old groups before changes
        if 'groups_id' in vals:
            old_groups = {user.id: set(user.groups_id.ids) for user in self}
        
        result = super(ResUsers, self).write(vals)
        
        # Post messages for group changes
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
                        group.message_post(
                            body=f"<b>User Added:</b> {user.display_name}<br/>"
                                 f"<b>Added by:</b> {current_user.display_name}",
                            subject="User Added to Group",
                            subtype_xmlid='mail.mt_note'
                        )
                
                # Groups removed from this user
                removed_groups = old_group_ids - new_group_ids
                if removed_groups:
                    groups = self.env['res.groups'].browse(list(removed_groups))
                    for group in groups:
                        group.message_post(
                            body=f"<b>User Removed:</b> {user.display_name}<br/>"
                                 f"<b>Removed by:</b> {current_user.display_name}",
                            subject="User Removed from Group",
                            subtype_xmlid='mail.mt_note'
                        )
        
        return result