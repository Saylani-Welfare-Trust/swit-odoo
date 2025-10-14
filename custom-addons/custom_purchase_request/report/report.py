from odoo import models, fields, api


class purchase_req_quot(models.TransientModel):
    _name = 'purchase_req.report'
    _description = 'purchase_req.report'


    def _get_report_values(self, docids, data=None):
        docs = self.env['custom.purchase.request'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'custom.purchase.request',
            'docs': docs,
        }