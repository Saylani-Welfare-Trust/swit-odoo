from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ResGroups(models.Model):
    _inherit = 'res.groups'

    user_count = fields.Integer(compute='_compute_user_info', store=True)
    user_names = fields.Char(compute='_compute_user_info', store=True)
    log_ids = fields.One2many('res.groups.log', 'group_id', string="Activity Log")

    @api.depends('users')
    def _compute_user_info(self):
        for group in self:
            group.user_count = len(group.users)
            group.user_names = ', '.join(group.users.mapped('display_name')) or 'No users'

    def _get_mail_thread_data(self, request_list):
        return {record.id: {'message_ids': [], 'log_ids': []} for record in self}

    def write(self, vals):
        if 'users' in vals:
            before_users = {}
            for group in self:
                before_users[group.id] = set(group.users.ids)
            
            res = super().write(vals)
            
            for group in self:
                after_users = set(group.users.ids)
                before = before_users[group.id]
                after = after_users
                
                if before != after:
                    added = after - before
                    removed = before - after
                    
                    details = []
                    if added:
                        added_names = self.env['res.users'].browse(list(added)).mapped('display_name')
                        details.append(f"Added: {', '.join(added_names)}")
                    if removed:
                        removed_names = self.env['res.users'].browse(list(removed)).mapped('display_name')
                        details.append(f"Removed: {', '.join(removed_names)}")
                    
                    note = f"Group '{group.display_name}' updated by {self.env.user.display_name}: {'; '.join(details)}"
                    
                    self.env['res.groups.log'].sudo().create({
                        'group_id': group.id,
                        'note': note,
                        'create_uid': self.env.user.id,
                    })
            
            return res
        
        return super().write(vals)


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    def write(self, vals):
        # Check for in_group_X fields
        group_field_changes = []
        for key in vals.keys():
            if key.startswith('in_group_'):
                group_id = int(key.split('_')[-1])
                group_field_changes.append((group_id, vals[key]))
        
        if group_field_changes or 'groups_id' in vals:
            before_groups = {}
            for user in self:
                before_groups[user.id] = set(user.groups_id.ids)
            
            res = super().write(vals)
            
            for user in self:
                after_groups = set(user.groups_id.ids)
                before = before_groups[user.id]
                after = after_groups
                
                if before != after:
                    added = after - before
                    removed = before - after
                    
                    for group_id in added | removed:
                        group = self.env['res.groups'].browse(group_id)
                        action = "added to" if group_id in added else "removed from"
                        note = f"User '{user.display_name}' was {action} group '{group.display_name}' by {self.env.user.display_name}"
                        
                        self.env['res.groups.log'].sudo().create({
                            'group_id': group.id,
                            'note': note,
                            'create_uid': self.env.user.id,
                        })
            
            return res
        
        return super().write(vals)


class ResGroupsLog(models.Model):
    _name = 'res.groups.log'
    _description = 'Groups Membership Log'
    _order = 'create_date desc'
    _rec_name = 'note'

    group_id = fields.Many2one('res.groups', ondelete='cascade', required=True)
    note = fields.Char(string="Change Description", required=True)
    create_date = fields.Datetime(string="Date", readonly=True, default=fields.Datetime.now)
    create_uid = fields.Many2one('res.users', string="Changed By", readonly=True)