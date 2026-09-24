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
        welfare = False
        if 'welfare' in self.env:
            Welfare = self.env['welfare'].sudo()
            if welfare_id:
                partners = partners.sudo()
                welfare = Welfare.browse(welfare_id)
            elif partners:
                # Printed from the donee form: use the donee's latest welfare application.
                # Not based on the 'Welfare' tag, older donees often don't have it.
                welfare = Welfare.search([('donee_id', '=', partners[:1].id)], order='id desc', limit=1) or False
        return {
            'doc_ids': docids,
            'doc_model': 'res.partner',
            'docs': partners,
            'data': data,
            'welfare': welfare,
        }
