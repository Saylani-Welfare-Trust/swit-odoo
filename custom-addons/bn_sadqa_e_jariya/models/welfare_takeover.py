# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Welfare versions that still handle institutions themselves (pre_production):
# their institution fetch menu (Fetch + Logs) and groups.
WELFARE_FETCH_MENU = 'bn_welfare.menu_fetch_institution_applications'
WELFARE_GROUPS = {
    'bn_welfare.group_fetch_institution': 'bn_sadqa_e_jariya.group_fetch_institution',
    'bn_welfare.group_institutional_disbursement': 'bn_sadqa_e_jariya.group_institutional_disbursement',
}
DONE_PARAM = 'bn_sadqa_e_jariya.welfare_institutions_taken_over'


class SadqaJariya(models.Model):
    _inherit = 'sadqa.jariya'

    @api.model
    def _take_over_welfare_institutions(self):
        """Every install / upgrade. Where Welfare still fetches institution
        applications itself (an older Welfare, e.g. pre_production), Sadqa e
        Jariya takes over: Welfare's "Fetch Institution Applications" menu is
        hidden, so applications only come in here. Institution applications
        already in Welfare stay there (Institution Disbursement) to be
        completed. Once: the users of Welfare's institution groups get the
        matching Sadqa e Jariya groups, with its menu. Nothing happens where
        Welfare no longer has these (Development and later)."""
        menu = self.env.ref(WELFARE_FETCH_MENU, raise_if_not_found=False)
        if menu and menu.active:
            menu.sudo().active = False
            _logger.info('Sadqa e Jariya: Welfare institution fetch menu hidden.')
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(DONE_PARAM):
            return
        root = self.env.ref('bn_sadqa_e_jariya.sadqa_e_jariya_root_group')
        moved = 0
        for old_xmlid, new_xmlid in WELFARE_GROUPS.items():
            old = self.env.ref(old_xmlid, raise_if_not_found=False)
            new = self.env.ref(new_xmlid, raise_if_not_found=False)
            if not old or not new or old == new:
                continue
            users = old.sudo().users
            if users:
                (new | root).sudo().write({'users': [(4, user.id) for user in users]})
                moved += len(users)
        if moved:
            _logger.info('Sadqa e Jariya: %s Welfare institution user(s) given the Sadqa e Jariya groups.', moved)
        params.set_param(DONE_PARAM, '1')
