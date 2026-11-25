from odoo import api, models


class ReportWelfareApprovalCertificate(models.AbstractModel):
    _name = 'report.bn_welfare.report_welfare_approval_certificate'
    _description = 'Welfare Approval Certificate'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        # printed with options (Final Approve): the web client sends the records as the context's active_ids
        docids = docids or data.get('context', {}).get('active_ids') or []
        return {
            'doc_ids': docids,
            'doc_model': 'welfare',
            'docs': self.env['welfare'].browse(docids),
            'skip_paid_hod': bool(data.get('skip_paid_hod')),
        }
