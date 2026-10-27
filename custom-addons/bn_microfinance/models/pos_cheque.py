from odoo import models, fields


class POSCheque(models.Model):
    _inherit = 'pos.cheque'

    def _get_microfinance_pdc_line(self):
        """Get the PDC line linked to this cheque"""
        self.ensure_one()
        return self.env['microfinance.pdc.line'].search([
            ('cheque_no', '=', self.name),
        ], limit=1)

    def _get_or_repair_microfinance_line(self, pdc_line):
        """Get microfinance line from link or fallback to installment_number search, and repair the link"""
        microfinance_line = pdc_line.microfinance_line_id
        if not microfinance_line and pdc_line.installment_number and pdc_line.microfinance_id:
            microfinance_line = self.env['microfinance.line'].search([
                ('microfinance_id', '=', pdc_line.microfinance_id.id),
                ('installment_no', '=', pdc_line.installment_number),
            ], limit=1)
            if microfinance_line:
                pdc_line.microfinance_line_id = microfinance_line.id  # self-heal
        return microfinance_line

    def _update_microfinance_pdc(self, state_cheque, paid):
        """Mirror the cheque state on its microfinance PDC line and installment."""
        # Treasury has no Microfinance rights: its group was checked by the caller
        for rec in self.sudo():
            pdc_line = rec._get_microfinance_pdc_line()
            if not pdc_line:
                continue
            pdc_line.write({'state_cheque': state_cheque})
            microfinance_line = rec._get_or_repair_microfinance_line(pdc_line)
            if not microfinance_line:
                continue
            if paid:
                microfinance_line.write({
                    'state': 'paid',
                    'paid_amount': microfinance_line.amount,
                    'payment_date': fields.Date.today(),
                })
            else:
                microfinance_line.write({
                    'state': 'unpaid',
                    'paid_amount': 0.0,
                    'payment_date': False,
                })

    def action_clear(self):
        res = super().action_clear()
        self._update_microfinance_pdc('cleared', paid=True)
        return res

    def action_bounce(self):
        res = super().action_bounce()
        self._update_microfinance_pdc('bounced', paid=False)
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._update_microfinance_pdc('draft', paid=False)
        return res
