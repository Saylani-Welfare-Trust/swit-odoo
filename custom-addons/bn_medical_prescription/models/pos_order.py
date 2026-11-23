from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    medical_prescription_id = fields.Many2one(
        'medical.prescription', 'Prescription', readonly=True, copy=False, index='btree_not_null')

    @api.model
    def _order_fields(self, ui_order):
        vals = super()._order_fields(ui_order)
        Prescription = self.env['medical.prescription'].sudo()
        prescription = Prescription.browse(int(ui_order.get('medical_prescription_id') or 0)).exists()
        vals['medical_prescription_id'] = prescription.id
        if prescription:
            # a medicine bill, not a donation
            vals['is_non_donation_receipt'] = True

        # an order that can't be synced is stuck in the POS: drop links to lines that don't exist anymore
        order_lines = [line[2] for line in vals.get('lines') or [] if line[2].get('medical_prescription_line_id')]
        if order_lines:
            existing = set(self.env['medical.prescription.line'].sudo().browse(
                {line['medical_prescription_line_id'] for line in order_lines}).exists().ids)
            for line in order_lines:
                if line['medical_prescription_line_id'] not in existing:
                    line['medical_prescription_line_id'] = False
        return vals

    def _process_order(self, order, draft, existing_order):
        order_id = super()._process_order(order, draft, existing_order)
        if not draft:
            pos_order = self.browse(order_id)
            if pos_order.medical_prescription_id:
                pos_order.medical_prescription_id.sudo()._mark_billed(pos_order)
        return order_id

    def _export_for_ui(self, order):
        result = super()._export_for_ui(order)
        result['medical_prescription_id'] = order.medical_prescription_id.id
        result['medical_prescription_name'] = order.medical_prescription_id.sudo().name or False
        return result


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    medical_prescription_line_id = fields.Many2one(
        'medical.prescription.line', 'Prescription Line', readonly=True, copy=False, index='btree_not_null')
