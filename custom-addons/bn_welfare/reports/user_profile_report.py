from odoo import models


class UserProfileReport(models.AbstractModel):
    _inherit = 'report.bn_profile_management.user_profile_report'

    def _get_welfare(self, partners, data):
        Welfare = self.env['welfare'].sudo()
        if data.get('welfare_id'):
            return Welfare.browse(data['welfare_id']), True
        if partners and 'Welfare' in partners[:1].category_id.mapped('name'):
            # Printed from the donee form: a Welfare-tagged donee always gets the
            # welfare form, filled from the latest application (empty if none)
            return Welfare.search([('donee_id', '=', partners[:1].id)], order='id desc', limit=1), True
        return super()._get_welfare(partners, data)
