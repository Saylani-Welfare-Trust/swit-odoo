from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'


    def _default_groups(self):
        """New users start without any group (Odoo would give them the groups
        of the Default User Template): access is only ever given on purpose.
        Uninstall this module to get Odoo's default back."""
        return []