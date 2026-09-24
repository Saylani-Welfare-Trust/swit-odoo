# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ArrangeBudgetWizard(models.TransientModel):
    _name = 'procurement.arrange.budget.wizard'
    _description = 'Arrange Budget for an RFQ'

    order_id = fields.Many2one('purchase.order', string='RFQ', required=True, readonly=True)
    line_ids = fields.One2many('procurement.arrange.budget.wizard.line', 'wizard_id', string='Transfers')

    @api.model
    def default_get(self, fields_list):
        """One line per segment that is short, pre-filled with the shortfall."""
        res = super().default_get(fields_list)
        order = self.env['purchase.order'].browse(self.env.context.get('default_order_id'))
        if order:
            res['order_id'] = order.id
            res['line_ids'] = [(0, 0, {
                'destination_id': analytic.id,
                'shortfall': required - balance,
                'amount': required - balance,
            }) for analytic, required, balance in order._get_shariah_shortfalls()]
        return res

    def action_confirm(self):
        """Move the money in Shariah Law (one Shariah transfer per line), then
        re-check the RFQ: once it fits the balance it is approved and its PO
        is created."""
        self.ensure_one()
        order = self.order_id
        if not self.env.user.has_group('bn_material_request.menu_group_material_request_cfo'):
            raise UserError(_('Only the CFO can arrange the budget.'))
        if not order.shariah_hold:
            raise UserError(_('This RFQ is not waiting for the CFO.'))
        transfer_model = self.env['shariah.transfer']
        transfers = transfer_model
        for line in self.line_ids:
            if not line.source_id:
                raise UserError(_('Choose the source segment to take the budget from for %s.') % line.destination_id.display_name)
            if line.amount <= 0:
                raise UserError(_('The amount to transfer to %s must be positive.') % line.destination_id.display_name)
            if line.amount > line.source_balance:
                raise UserError(_(
                    '%(source)s only has %(balance).2f available, which is less than the %(amount).2f to transfer.'
                ) % {'source': line.source_id.display_name, 'balance': line.source_balance, 'amount': line.amount})
            # The CFO can move budget from any segment here - the Segment Transfer
            # Rules that gate a normal manual Shariah transfer are not enforced for
            # this wizard, only the source having enough balance (checked above).
            transfer = transfer_model.create({
                'source_analytic_account_id': line.source_id.id,
                'destination_analytic_account_id': line.destination_id.id,
                'amount': line.amount,
                'note': _('Budget arranged by the CFO for RFQ %s') % order.display_name,
            })
            transfer.action_post()
            transfers |= transfer
        order._after_budget_arranged(transfers)
        return {'type': 'ir.actions.act_window_close'}


class ArrangeBudgetWizardLine(models.TransientModel):
    _name = 'procurement.arrange.budget.wizard.line'
    _description = 'Arrange Budget Line'

    wizard_id = fields.Many2one('procurement.arrange.budget.wizard', required=True, ondelete='cascade')
    destination_id = fields.Many2one(
        'account.analytic.account', string='Segment Short of Budget', required=True,
        domain="[('plan_id.name', '=', 'Segment')]")
    shortfall = fields.Float(string='Shortfall', readonly=True)
    # Any Segment analytic account can be the source here - not filtered by the
    # Segment Transfer Rules that gate a normal manual Shariah transfer - other
    # than not letting a segment be its own source.
    source_id = fields.Many2one(
        'account.analytic.account', string='Take Budget From',
        domain="[('plan_id.name', '=', 'Segment'), ('id', '!=', destination_id)]")
    source_balance = fields.Float(string='Available There', compute='_compute_source_balance')
    amount = fields.Float(string='Amount to Transfer')

    @api.depends('source_id')
    def _compute_source_balance(self):
        for line in self:
            line.source_balance = self.env['shariah.law'].get_closing_balance(line.source_id.id) if line.source_id else 0.0
