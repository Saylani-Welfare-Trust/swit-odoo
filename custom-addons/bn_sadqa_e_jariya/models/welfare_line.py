from odoo import models


class WelfareLine(models.Model):
    _inherit = 'welfare.line'

    def _get_pending_welfare_extra_vals(self, welfare):
        vals = super()._get_pending_welfare_extra_vals(welfare)
        vals.update({
            'institution_category': welfare.institution_category if welfare.institution_category else False,
            'subcategory': welfare.subcategory if welfare.subcategory else False,
        })
        return vals
