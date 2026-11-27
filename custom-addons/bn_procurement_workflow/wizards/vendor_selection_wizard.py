# -*- coding: utf-8 -*-
from odoo import api, models, fields, _


class VendorSelectionWizard(models.TransientModel):
    _inherit = 'vendor.selection.wizard'
    
    designated_cxo_approver_id = fields.Many2one(
        'master.cxo.approver', 
        string='Assigned CXO Approver',
        help='If set, ONLY this user can give CXO approval to this RFQ.'
    )

    @api.model
    def default_get(self, fields_list):
        """The "Procurement Manager Approval" page offers the lines of other
        requests, whose vendors this user would select too: not of the
        requests assigned to someone else."""
        res = super().default_get(fields_list)
        commands = res.get('procurement_line_ids')
        if commands:
            lines = self.env['purchase.requisition.line'].browse(
                [vals['requisition_line_id'] for _command, _id, vals in commands])
            allowed = lines.filtered(lambda line: line.requisition_id.is_rfq_creator_allowed)
            res['procurement_line_ids'] = [
                command for command in commands if command[2]['requisition_line_id'] in allowed.ids]
        return res

    def action_create_rfqs(self):
        requisition = self.source_requisition_id
        (requisition | self.procurement_line_ids.filtered('selected').requisition_line_id.requisition_id
         )._check_rfq_creator()
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
        # It only moves on to RFQ Sent once every line is on an RFQ: until then it
        # stays in Procurement Manager Approval, so the RFQs for the remaining
        # products are created from the same button.
        if requisition:
            if state_before == 'procurement_approval' and not requisition._get_lines_to_rfq():
                requisition.state = 'rfq_sent'
            else:
                requisition.state = state_before
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
