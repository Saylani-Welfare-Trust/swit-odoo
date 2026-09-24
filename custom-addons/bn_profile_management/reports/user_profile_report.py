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
        if welfare_id:
            partners = partners.sudo()
            welfare = self.env['welfare'].sudo().browse(welfare_id)
        return {
            'doc_ids': docids,
            'doc_model': 'res.partner',
            'docs': partners,
            'data': data,
            'welfare': welfare,
        }
