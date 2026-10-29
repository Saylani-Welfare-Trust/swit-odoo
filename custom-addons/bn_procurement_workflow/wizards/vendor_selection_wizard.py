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
        requisition._check_rfq_creator()
        # RFQs can be created on the same Purchase Request more than once (a
        # batch at a time): the first batch in Procurement Manager Approval,
        # later ones in RFQ Sent or further along.
        state_before = requisition.state
        result = super().action_create_rfqs()

        # super() returns the RFQ's form action when it created exactly one
        # RFQ, and the RFQs themselves otherwise.
        if isinstance(result, dict):
            rfqs = self.env['purchase.order'].browse(result['res_id'])
        else:
            rfqs = result

        # super() closes a Purchase Request once all its lines are on RFQs, but
        # here its RFQs still go through winner selection, CXO approval and the
        # funds check: it closes once their Purchase Orders are confirmed.
        if requisition:
            requisition.state = 'rfq_sent' if state_before == 'procurement_approval' else state_before
        # After the state: in RFQ Sent the new RFQs await selection, so the
        # approver's email is held back until then.
        rfqs.write({'designated_cxo_approver_id': self.designated_cxo_approver_id.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('RFQs Created'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', rfqs.ids)],
            'target': 'current',
        }
