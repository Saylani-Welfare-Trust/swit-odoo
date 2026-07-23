from odoo import api, fields, models


class ResGroups(models.Model):
    _inherit = ['res.groups', 'mail.thread', 'mail.activity.mixin']

    user_count = fields.Integer(
        string="Count",
        compute='_compute_user_info',
        store=True,
        tracking=True,
    )

    user_names = fields.Char(
        string="Names",
        compute='_compute_user_info',
        store=True,
        tracking=True,
    )

    @api.depends('users')
    def _compute_user_info(self):
        for group in self:
            group.user_count = len(group.users)
            group.user_names = ', '.join(group.users.mapped('display_name')) if group.users else 'No users'

    def write(self, vals):
        old_users_by_group = {}
        if 'users' in vals:
            old_users_by_group = {group.id: group.users for group in self}

        result = super().write(vals)

        if 'users' in vals:
            current_user = self.env.user
            for group in self:
                old_users = old_users_by_group.get(group.id, self.env['res.users'])
                new_users = group.users

                added_users = new_users - old_users
                removed_users = old_users - new_users

                if added_users:
                    group.message_post(
                        body=f"<b>Users Added:</b> {', '.join(added_users.mapped('display_name'))}<br/>"
                             f"<b>Added by:</b> {current_user.display_name}<br/>"
                             f"<b>Total Users:</b> {group.user_count}<br/>"
                             f"<b>All Users:</b> {group.user_names}",
                        subject="Users Added to Group",
                        subtype_xmlid='mail.mt_note',
                    )

                if removed_users:
                    group.message_post(
                        body=f"<b>Users Removed:</b> {', '.join(removed_users.mapped('display_name'))}<br/>"
                             f"<b>Removed by:</b> {current_user.display_name}<br/>"
                             f"<b>Total Users:</b> {group.user_count}<br/>"
                             f"<b>All Users:</b> {group.user_names}",
                        subject="Users Removed from Group",
                        subtype_xmlid='mail.mt_note',
                    )

        return result


class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, vals):
        old_groups = {}
        if 'groups_id' in vals:
            old_groups = {user.id: set(user.groups_id.ids) for user in self}

        result = super().write(vals)

        if 'groups_id' in vals:
            current_user = self.env.user
            for user in self:
                new_group_ids = set(user.groups_id.ids)
                old_group_ids = old_groups.get(user.id, set())

                added_groups = self.env['res.groups'].browse(list(new_group_ids - old_group_ids))
                for group in added_groups:
                    group.message_post(
                        body=f"<b>User Added:</b> {user.display_name}<br/>"
                             f"<b>Added by:</b> {current_user.display_name}<br/>"
                             f"<b>Total Users:</b> {group.user_count}<br/>"
                             f"<b>All Users:</b> {group.user_names}",
                        subject="User Added to Group",
                        subtype_xmlid='mail.mt_note',
                    )

                removed_groups = self.env['res.groups'].browse(list(old_group_ids - new_group_ids))
                for group in removed_groups:
                    group.message_post(
                        body=f"<b>User Removed:</b> {user.display_name}<br/>"
                             f"<b>Removed by:</b> {current_user.display_name}<br/>"
                             f"<b>Total Users:</b> {group.user_count}<br/>"
                             f"<b>All Users:</b> {group.user_names}",
                        subject="User Removed from Group",
                        subtype_xmlid='mail.mt_note',
                    )

        return result