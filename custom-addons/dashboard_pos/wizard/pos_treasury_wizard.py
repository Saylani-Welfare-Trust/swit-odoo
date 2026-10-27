from odoo import models, fields, api

class PosTreasuryWizard(models.TransientModel):
    _name = 'pos.treasury.wizard'
    _description = 'POS Treasury Analysis Wizard'

    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    config_id = fields.Many2one('pos.config', string="Shop")

    def _get_base_domain(self):
        domain = []
        if self.date_from:
            domain.append(('date_order', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_order', '<=', self.date_to))
        if self.config_id:
            domain.append(('config_id', '=', self.config_id.id))
        return domain

    def action_view_cheques(self):
        domain = self._get_base_domain()
        domain.append(('pos_cheque_id', '!=', False))
        return self._get_action('POS Orders with Cheques', domain)

    def action_view_deposits(self):
        domain = self._get_base_domain()
        # Adjust this domain if you link deposits differently (e.g., via a specific field)
        domain.append(('payment_ids.payment_method_id.name', 'ilike', 'Deposit'))
        return self._get_action('POS Orders with Direct Deposits', domain)

    def action_view_transfers(self):
        domain = self._get_base_domain()
        # Adjust this domain if you link transfers differently
        domain.append(('payment_ids.payment_method_id.name', 'ilike', 'Transfer'))
        return self._get_action('POS Orders with Journal Transfers', domain)

    def _get_action(self, name, domain):
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
        }