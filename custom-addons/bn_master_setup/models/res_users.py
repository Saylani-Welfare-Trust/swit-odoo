from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'


    def _default_groups(self):
        """Default groups for employees

        All the groups of the Template User
        """
        # default_user = self.env.ref('base.default_user', raise_if_not_found=False)
        # return default_user.sudo().groups_id if default_user else []

        return []