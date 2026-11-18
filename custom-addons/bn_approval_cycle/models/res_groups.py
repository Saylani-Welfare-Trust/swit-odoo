# -*- coding: utf-8 -*-
from odoo import api, models


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.model
    def _approval_cycle_menu_upgrade(self):
        """Once: the users of "Approval User" (which also opened the app before
        the Menu group existed) get the Menu group."""
        Param = self.env['ir.config_parameter'].sudo()
        if Param.get_param('access_structure.bn_approval_cycle.tiers'):
            return
        Param.set_param('access_structure.bn_approval_cycle.tiers', '1')
        user = self.env.ref('bn_approval_cycle.group_approval_user', raise_if_not_found=False)
        menu = self.env.ref('bn_approval_cycle.group_approval_root', raise_if_not_found=False)
        if user and menu and user.users:
            menu.sudo().write({'users': [(4, u.id) for u in user.sudo().users]})
