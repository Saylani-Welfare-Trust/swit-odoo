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
        old_users_by_group = {group.id: group.users for group in self} if 'users' in vals else {}

        result = super().write(vals)

        if 'users' in vals:
            current_user = self.env.user
            for group in self:
                old_users = old_users_by_group.get(group.id, self.env['res.users'])
                new_users = group.users

                added = new_users - old_users
                removed = old_users - new_users

                if added:
                    group.message_post(
                        body=f"<b>Added:</b> {', '.join(added.mapped('display_name'))} "
                             f"<b>by</b> {current_user.display_name}"
                    )

                if removed:
                    group.message_post(
                        body=f"<b>Removed:</b> {', '.join(removed.mapped('display_name'))} "
                             f"<b>by</b> {current_user.display_name}"
                    )

        return result