# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.model
    def _keep_pre_production_collection_read(self):
        """Upgrade of a pre_production database: there every internal user
        could read rider collections, so the Donation Box dashboard showed
        them to its Managers and Audit users. Here collections are for the
        Rider Shift groups: those users get the read-only Rider Shift Audit
        group so the dashboard keeps its figures. pre_production is recognised
        by its "POS Action" group (removed by this upgrade); nothing is done
        on any other database or on a fresh install."""
        if not self.env.ref('bn_donation_box.donation_box_pos_action_group', raise_if_not_found=False):
            return
        audit = self.env.ref('bn_rider_shift.rider_shift_audit_group')
        users = self.browse()
        for xmlid in ('bn_donation_box.donation_box_manager_group', 'bn_donation_box.donation_box_audit_group'):
            users |= self.env.ref(xmlid, raise_if_not_found=False) or self.browse()
        users = users.sudo().users - audit.sudo().users
        if users:
            audit.sudo().write({'users': [(4, user.id) for user in users]})
            _logger.info('Rider Shift Audit given to %d Donation Box Manager / Audit user(s).', len(users))
