# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError


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
        if requisition and (requisition.state != 'procurement_approval' or not requisition.procurement_manager_id):
            raise ValidationError(
                _('RFQs can only be created once the Procurement Manager has approved this '
                  'Purchase Requisition for RFQ.'))
        results = super().action_create_rfqs()
        
        for result in results:
            result.designated_cxo_approver_id = self.designated_cxo_approver_id.id
        
        if requisition:
            requisition.action_mark_rfq_sent()
        return {
            'type': 'ir.actions.act_window',
            'name': _('RFQs Created'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', results.ids)],
            'target': 'current',
        }
