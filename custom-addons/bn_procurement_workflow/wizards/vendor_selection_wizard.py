# -*- coding: utf-8 -*-
from odoo import models, fields, _


class VendorSelectionWizard(models.TransientModel):
    _inherit = 'vendor.selection.wizard'
    
    designated_cxo_approver_id = fields.Many2one(
        'master.cxo.approver', 
        string='Assigned CXO Approver', 
        tracking=True,
        help='If set, ONLY this user can give CXO approval to this RFQ.'
    )

    def action_create_rfqs(self):
        requisition = self.source_requisition_id
        # RFQs can be created on the same Purchase Request more than once (a
        # batch at a time), so it is either still in Procurement Manager
        # Approval (first batch) or already in RFQ Sent (a later batch).
        in_rfq_stage = requisition.state in ('procurement_approval', 'rfq_sent')
        result = super().action_create_rfqs()

        # super() returns the RFQ's form action when it created exactly one
        # RFQ, and the RFQs themselves otherwise.
        if isinstance(result, dict):
            rfqs = self.env['purchase.order'].browse(result['res_id'])
        else:
            rfqs = result
        rfqs.write({'designated_cxo_approver_id': self.designated_cxo_approver_id.id})

        # super() closes a Purchase Request once all its lines are ordered, but
        # here its RFQs still go through winner selection, CXO approval and the
        # funds check, which all need it in RFQ Sent.
        if requisition and in_rfq_stage:
            requisition.state = 'rfq_sent'
        return {
            'type': 'ir.actions.act_window',
            'name': _('RFQs Created'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', rfqs.ids)],
            'target': 'current',
        }
