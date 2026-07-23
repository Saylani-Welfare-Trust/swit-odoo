# models/res_users.py
from odoo import api, fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'
    
    def write(self, vals):
        if 'groups_id' in vals:
            old_groups = {user.id: set(user.groups_id.ids) for user in self}
        
        result = super(ResUsers, self).write(vals)
        
        if 'groups_id' in vals:
            current_user = self.env.user
            for user in self:
                new_group_ids = set(user.groups_id.ids)
                old_group_ids = old_groups.get(user.id, set())
                
                added_groups = new_group_ids - old_group_ids
                if added_groups:
                    groups = self.env['res.groups'].browse(list(added_groups))
                    for group in groups:
                        group.message_post(
                            body=f"User <b>{user.display_name}</b> added to this group by <b>{current_user.display_name}</b>",
                            subject="User Added"
                        )
                
                removed_groups = old_group_ids - new_group_ids
                if removed_groups:
                    groups = self.env['res.groups'].browse(list(removed_groups))
                    for group in groups:
                        group.message_post(
                            body=f"User <b>{user.display_name}</b> removed from this group by <b>{current_user.display_name}</b>",
                            subject="User Removed"
                        )
        
        return result