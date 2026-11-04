from odoo import fields, models


class POSCheque(models.Model):
    _inherit = 'pos.cheque'

    source_model = fields.Selection(selection_add=[('welfare', 'Welfare')])
    welfare_line_ids = fields.Many2many(
        'welfare.line',
        'pos_cheque_welfare_line_rel_v2',
        'pos_cheque_id',
        'welfare_line_id',
        string="Welfare Lines",
    )
    welfare_recurring_line_ids = fields.Many2many(
        'welfare.recurring.line',
        'pos_cheque_welfare_recurring_line_rel_v2',
        'pos_cheque_id',
        'welfare_recurring_line_id',
        string="Welfare Recurring Lines",
    )

    def _clear_welfare(self):
        self.ensure_one()
        # call the real action, not a raw write — this also handles
        # advance_donation_line_id disbursement creation and calls
        # welfare_id._auto_disburse_if_all_lines_delivered() internally
        payable_lines = self.welfare_line_ids.filtered(lambda l: l.state in ('draft', 'delivered'))
        if payable_lines:
            payable_lines.action_disbursed()

        payable_recurring = self.welfare_recurring_line_ids.filtered(lambda l: l.state in ('draft', 'delivered'))
        if payable_recurring:
            payable_recurring.action_disbursed()

    def _bounce_welfare(self):
        self.ensure_one()
        lines = self.welfare_line_ids
        recurring_lines = self.welfare_recurring_line_ids

        if lines:
            lines.write({'state': 'draft'})
            lines.mapped('welfare_id').filtered(
                lambda w: w.state == 'disbursed'
            ).write({'state': 'approve'})

        if recurring_lines:
            recurring_lines.write({'state': 'draft'})
            recurring_lines.mapped('welfare_id').filtered(
                lambda w: w.state == 'disbursed'
            ).write({'state': 'recurring'})

    def action_clear(self):
        res = super().action_clear()
        for rec in self.filtered(lambda c: c.source_model == 'welfare'):
            rec.sudo()._clear_welfare()
        return res

    def action_bounce(self):
        res = super().action_bounce()
        for rec in self.filtered(lambda c: c.source_model == 'welfare'):
            rec.sudo()._bounce_welfare()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        for rec in self.filtered(lambda c: c.source_model == 'welfare'):
            rec.sudo()._bounce_welfare()  # same reset as bounce
        return res


class POSOrder(models.Model):
    _inherit = 'pos.order'

    def _prepare_pos_cheque_vals(self, ui_order, vals):
        vals = super()._prepare_pos_cheque_vals(ui_order, vals)
        welfare_data = (ui_order.get('extra_data') or {}).get('welfare')
        if welfare_data:
            vals['source_model'] = 'welfare'
            vals['source_record_id'] = welfare_data.get('welfare_id')
            line_ids = [l['id'] for l in (welfare_data.get('welfare_line_ids') or []) if l.get('id')]
            recurring_ids = [l['id'] for l in (welfare_data.get('recurring_line_ids') or []) if l.get('id')]
            if line_ids:
                vals['welfare_line_ids'] = [(6, 0, line_ids)]
            if recurring_ids:
                vals['welfare_recurring_line_ids'] = [(6, 0, recurring_ids)]
        return vals
