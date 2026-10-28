from odoo import models, fields, api, _


class DirectDeposit(models.Model):
    _inherit = 'direct.deposit'

    qurbani_order_id = fields.Many2one('qurbani.order', string="Qurbani Order")
    favor = fields.Char('Favor')

    def action_not_clear(self):
        self._check_dd_treasury()
        self._check_dd_state(('draft',), _('Not Clear'))
        # free the hissa booked for the qurbani of an unpaid deposit
        self.qurbani_order_id._release_booked_hissa()
        return super().action_not_clear()

    @api.model
    def create_dd_record(self, data):
        result = super().create_dd_record(data)

        if not result or result.get('status') != 'success':
            return result

        dd = self.sudo().browse(result['id'])

        favor = data.get('favor')
        if favor:
            dd.favor = favor

        # no Qurbani for medical equipment / welfare / microfinance deposits
        if data.get('source_request_type') not in ('Medical Equipment', 'Welfare', 'Microfinance'):
            dd.qurbani_order_id = self.env['qurbani.order']._book_qurbani(data)

        return result
