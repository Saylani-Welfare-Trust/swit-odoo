# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, _
from odoo.exceptions import ValidationError

CFO_GROUP = 'bn_material_request.menu_group_material_request_cfo'


class MaterialRequest(models.Model):
    _inherit = 'material.request'

    state = fields.Selection(
        selection_add=[('shariah_hold', 'Shariah Hold')],
        ondelete={'shariah_hold': 'set default'})

    shariah_hold_previous_state = fields.Char(string='State Before Shariah Hold', readonly=True, copy=False)
    shariah_hold_reason = fields.Text(string='Shariah Hold Reason', readonly=True, copy=False)
    shariah_override = fields.Boolean(
        string='Shariah Balance Overridden', readonly=True, copy=False, tracking=True,
        help='Set once the CFO has approved this request despite it exceeding the Shariah Law closing balance.')

    def _get_shariah_shortfalls(self):
        """Segments whose Shariah Law closing balance is below what this
        request's lines commit to that segment: [(analytic, required, balance)]."""
        self.ensure_one()
        blocker = self.env['shariah.law.blocker'].get_blocker_config()
        if not (blocker and blocker.enable_material_request):
            return []
        amounts = defaultdict(float)
        for line in self.line_ids:
            analytic = line.analytic_account_id or self.env['account.analytic.account'].search(
                [('product_ids', 'in', [line.product_id.id])], limit=1)
            if analytic:
                amounts[analytic.id] += line.subtotal
        return self.env['shariah.law'].get_shortfalls(amounts)

    def _shariah_hold_gate(self):
        """Put the request on Shariah Hold instead of letting the current
        approval through when it exceeds the Shariah Law balance. Only the CFO
        can release it, after which it returns to the state it was held in."""
        self.ensure_one()
        if self.shariah_override:
            return False
        shortfalls = self._get_shariah_shortfalls()
        if not shortfalls:
            return False
        reason = '\n'.join(
            _('%(segment)s: required %(required).2f, Shariah closing balance %(balance).2f') % {
                'segment': analytic.display_name, 'required': required, 'balance': balance}
            for analytic, required, balance in shortfalls)
        self.write({
            'shariah_hold_previous_state': self.state,
            'shariah_hold_reason': reason,
            'state': 'shariah_hold',
        })
        self.message_post(body=_(
            'Put on Shariah Hold - the amount exceeds the Shariah Law balance. '
            'Only the CFO can approve or reject it.<br/>%s') % reason.replace('\n', '<br/>'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shariah Hold'),
                'message': _('The amount exceeds the Shariah Law balance. The request is on hold until the CFO approves or rejects it.'),
                'type': 'warning',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _check_shariah_cfo(self):
        self.ensure_one()
        if self.state != 'shariah_hold':
            raise ValidationError(_('This request is not on Shariah Hold.'))
        if not self.env.user.has_group(CFO_GROUP):
            raise ValidationError(_('Only the CFO can approve or reject a Shariah Hold.'))

    def action_shariah_hold_approve(self):
        """CFO releases the hold: the request goes back to the state it was
        held in and the normal flow carries on from there."""
        self.ensure_one()
        self._check_shariah_cfo()
        previous_state = self.shariah_hold_previous_state or 'hod_approval'
        self.write({
            'state': previous_state,
            'shariah_override': True,
            'shariah_hold_previous_state': False,
            'shariah_hold_reason': False,
        })
        self.message_post(body=_('Shariah Hold approved by CFO %(user)s - request returned to its previous stage.') % {
            'user': self.env.user.display_name})
        return True

    def action_shariah_hold_reject(self):
        """CFO rejects the held request."""
        self.ensure_one()
        self._check_shariah_cfo()
        self.action_reject()
        self.write({'shariah_hold_previous_state': False})
        self.message_post(body=_('Shariah Hold rejected by CFO %(user)s.') % {'user': self.env.user.display_name})
        return True

    def action_reset_to_draft(self):
        res = super().action_reset_to_draft()
        self.write({
            'shariah_override': False,
            'shariah_hold_previous_state': False,
            'shariah_hold_reason': False,
        })
        return res
