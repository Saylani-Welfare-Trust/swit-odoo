from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    comparative_count = fields.Integer('Comparative Count', compute="_set_comparative_count")


    def _set_comparative_count(self):
        for rec in self:
            rec.comparative_count = 0

            if rec.requisition_id:
                rec.comparative_count = len(rec.requisition_id.purchase_ids.filtered(lambda p: p.id != rec.id))

    def action_open_comparative_analysis(self):
        purchase_ids = self.requisition_id.purchase_ids.filtered(lambda p: p.id != self.id)

        # raise ValidationError(str(purchase_ids))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Request for Quotations',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', purchase_ids.ids)],
            'context': {
                'create': 0
            }
        }