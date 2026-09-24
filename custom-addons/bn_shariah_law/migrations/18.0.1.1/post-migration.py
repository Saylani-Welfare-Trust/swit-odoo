# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """One-off: switch the Purchase Orders blocker on for every company, so RFQs
    are checked against the Shariah Law balance. It had been left off by the
    initial data; it can still be switched off again on the blocker screen."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['shariah.law.blocker'].search([]).write({'enable_purchase': True})
