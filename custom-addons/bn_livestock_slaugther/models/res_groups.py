# -*- coding: utf-8 -*-
import logging

from odoo import api, models
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

# Documents whose authors already worked in the app before it had groups
LIVESTOCK_TABLES = ('livestock_slaugther', 'livestock_requisition', 'livestock_cutting',
                    'livestock_cutting_material', 'meat_management', 'distribution_center')


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.model
    def _livestock_first_tier_users(self):
        """Livestock was open to every internal user. On the first upgrade with
        the tiers, the users who created or edited its documents get Menu +
        User, so nobody loses access. Once only; nothing on a fresh install."""
        Param = self.env['ir.config_parameter'].sudo()
        key = 'access_structure.bn_livestock_slaugther.tiers'
        if Param.get_param(key):
            return
        Param.set_param(key, '1')
        cr = self.env.cr
        user_ids = set()
        for table in LIVESTOCK_TABLES:
            if table_exists(cr, table):
                cr.execute('SELECT DISTINCT create_uid FROM %s UNION SELECT DISTINCT write_uid FROM %s' % (table, table))
                user_ids |= {row[0] for row in cr.fetchall() if row[0]}
        users = self.env['res.users'].sudo().browse(user_ids).exists().filtered(
            lambda u: u.active and not u.share and u.id != self.env.ref('base.user_root').id)
        if not users:
            return
        groups = self.env.ref('bn_livestock_slaugther.livestock_slaugther_menu_group') \
            | self.env.ref('bn_livestock_slaugther.livestock_slaugther_user_group')
        groups.sudo().write({'users': [(4, user.id) for user in users]})
        _logger.info('Livestock Slaughter: %d existing user(s) given Menu + User', len(users))
