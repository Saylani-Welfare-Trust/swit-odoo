# -*- coding: utf-8 -*-
from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def write(self, vals):
        res = super().write(vals)
        # The registration record rule reads the employee's analytic account, and
        # record rule domains are cached per user: drop the cache when it changes.
        if 'analytic_account_id' in vals or 'user_id' in vals:
            self.env.registry.clear_cache()
        return res
