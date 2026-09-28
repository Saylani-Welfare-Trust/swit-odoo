from odoo import models


class UserProfileReport(models.AbstractModel):
    _name = 'report.bn_profile_management.user_profile_report'
    _description = 'User Profile Report'

    def _get_report_values(self, docids, data=None):
        data = data or {}
        welfare_id = data.get('welfare_id')
        # When printed from Welfare, ids come through `data` because
        # Odoo drops the action context for PDF downloads.
        docids = docids or data.get('partner_ids') or []
        partners = self.env['res.partner'].browse(docids)
        is_welfare = False
        welfare = False
        if 'welfare' in self.env:
            Welfare = self.env['welfare'].sudo()
            if welfare_id:
                partners = partners.sudo()
                welfare = Welfare.browse(welfare_id)
                is_welfare = True
            elif partners and 'Welfare' in partners[:1].category_id.mapped('name'):
                # Printed from the donee form: a Welfare-tagged donee always gets the
                # welfare form, filled from the latest application (empty if none)
                welfare = Welfare.search([('donee_id', '=', partners[:1].id)], order='id desc', limit=1)
                is_welfare = True
        return {
            'doc_ids': docids,
            'doc_model': 'res.partner',
            'docs': partners,
            'data': data,
            'welfare': welfare,
            'is_welfare': is_welfare,
        }
