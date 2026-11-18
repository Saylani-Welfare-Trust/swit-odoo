from odoo import models


class UserProfileReport(models.AbstractModel):
    _name = 'report.bn_profile_management.user_profile_report'
    _description = 'User Profile Report'

    def _get_report_values(self, docids, data=None):
        data = data or {}
        # When printed from Welfare, ids come through `data` because
        # Odoo drops the action context for PDF downloads.
        docids = docids or data.get('partner_ids') or []
        partners = self.env['res.partner'].browse(docids)
        welfare, is_welfare = self._get_welfare(partners, data)
        if is_welfare and data.get('welfare_id'):
            partners = partners.sudo()
        return {
            'doc_ids': docids,
            'doc_model': 'res.partner',
            'docs': partners,
            'data': data,
            'welfare': welfare,
            'is_welfare': is_welfare,
        }

    def _get_welfare(self, partners, data):
        """(welfare application, printed as the Welfare form). bn_welfare
        fills it in."""
        return False, False
