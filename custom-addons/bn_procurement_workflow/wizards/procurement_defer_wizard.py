# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProcurementDeferWizard(models.TransientModel):
    _name = 'procurement.defer.wizard'
    _description = 'Defer a Purchase Requisition'

    requisition_id = fields.Many2one('purchase.requisition', string='Purchase Requisition', required=True)
    defer_reason = fields.Text(string='Deferral Reason', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            res['requisition_id'] = active_id
        return res

    def action_confirm_defer(self):
        self.ensure_one()
        if not self.defer_reason:
            raise ValidationError(_('Please provide a deferral reason.'))
        self.requisition_id.action_procurement_defer(self.defer_reason)
        return {'type': 'ir.actions.act_window_close'}
