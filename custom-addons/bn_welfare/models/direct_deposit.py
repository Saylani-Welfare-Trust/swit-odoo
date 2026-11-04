from odoo import _, fields, models
from odoo.exceptions import UserError


class DirectDeposit(models.Model):
    _inherit = 'direct.deposit'

    source_model = fields.Selection(selection_add=[('welfare', 'Welfare')], ondelete={'welfare': 'set null'})
    welfare_line_ids = fields.Many2many(
        'welfare.line',
        'direct_deposit_welfare_line_rel',
        'direct_deposit_id',
        'welfare_line_id',
        string="Welfare Lines",
    )
    welfare_recurring_line_ids = fields.Many2many(
        'welfare.recurring.line',
        'direct_deposit_welfare_recurring_line_rel',
        'direct_deposit_id',
        'welfare_recurring_line_id',
        string="Welfare Recurring Lines",
    )

    def _prepare_dd_source_vals(self, data):
        if data.get('source_request_type') != 'Welfare' or not data.get('source_request_no'):
            return super()._prepare_dd_source_vals(data)

        source_request_no = data['source_request_no']
        welfare = self.env['welfare'].sudo().search(
            ['|', ('name', '=', source_request_no), ('old_system_id', '=', source_request_no)], limit=1)
        if not welfare:
            raise UserError(_('Welfare request %s was not found.') % source_request_no)

        vals = {'source_model': 'welfare', 'source_record_id': welfare.id}
        # only lines of this request
        line_ids = [l['id'] for l in (data.get('source_welfare_line_ids') or []) if l.get('id')]
        recurring_ids = [l['id'] for l in (data.get('source_welfare_recurring_line_ids') or []) if l.get('id')]
        if line_ids:
            vals['welfare_line_ids'] = [(6, 0, welfare.welfare_line_ids.filtered(lambda l: l.id in line_ids).ids)]
        if recurring_ids:
            vals['welfare_recurring_line_ids'] = [(6, 0, welfare.welfare_recurring_line_ids.filtered(
                lambda l: l.id in recurring_ids).ids)]
        return vals

    def _clear_source(self):
        if self.source_model != 'welfare':
            return super()._clear_source()
        lines = self.welfare_line_ids.sudo().filtered(lambda l: l.state in ('draft', 'delivered'))
        if lines:
            lines.action_disbursed()
        recurring_lines = self.welfare_recurring_line_ids.sudo().filtered(lambda l: l.state in ('draft', 'delivered'))
        if recurring_lines:
            recurring_lines.action_disbursed()
        return True
