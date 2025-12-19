from odoo import models, api


class DirectDepositReport(models.AbstractModel):
    _name = 'report.bn_direct_deposit.direct_deposit_receipt_template'
    _description = 'Direct Deposit Receipt Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Ensure data is always available in the report context"""
        if data is None:
            data = {}
        
        # When data is passed, docids might be in data['ids'] or data['context']['active_ids']
        if not docids and data:
            docids = data.get('ids') or data.get('context', {}).get('active_ids', [])
        
        # Default is_duplicate to False if not provided
        if 'is_duplicate' not in data:
            data['is_duplicate'] = False
        
        docs = self.env['direct.deposit'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'direct.deposit',
            'docs': docs,
            'data': data,
        }

