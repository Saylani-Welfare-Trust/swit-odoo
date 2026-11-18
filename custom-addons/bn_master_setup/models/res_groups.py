# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.model
    def _move_retired_group_users(self, moves, once_key=None):
        """Before a module's upgrade removes groups it no longer declares:
        their users get the group that replaces them, so nobody loses access.
        ``moves``: {retired group xmlid: replacing group xmlid or [xmlids]}.
        Called from each module's data (runs before the old groups are
        deleted at the end of the upgrade); does nothing on a fresh install.
        ``once_key``: for groups that are kept (e.g. Menu users becoming
        User when a module gets its tiers), done on the first upgrade only."""
        Param = self.env['ir.config_parameter'].sudo()
        if once_key:
            key = 'access_structure.%s' % once_key
            if Param.get_param(key):
                return
            Param.set_param(key, '1')
            if not self.env['ir.module.module'].sudo().search_count(
                    [('name', '=', once_key.split('.')[0]), ('state', 'in', ('installed', 'to upgrade'))]):
                return   # fresh install: nobody to move
        for old_xmlid, new_xmlids in moves.items():
            old = self.env.ref(old_xmlid, raise_if_not_found=False)
            if not old or not old.users:
                continue
            new = self.browse()
            for xmlid in ([new_xmlids] if isinstance(new_xmlids, str) else new_xmlids):
                new |= self.env.ref(xmlid, raise_if_not_found=False) or self.browse()
            if not new:
                continue
            users = old.sudo().users
            new.sudo().write({'users': [(4, user.id) for user in users]})
            _logger.info('%s: %d user(s) moved to %s', old_xmlid, len(users), ', '.join(new_xmlids)
                         if not isinstance(new_xmlids, str) else new_xmlids)
