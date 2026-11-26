from odoo import models

# The prescription numbers restart every day: RX/26112026/0001
DAILY_SEQUENCE_CODES = {'medical.prescription'}


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    def _create_date_range_seq(self, date):
        if self.code not in DAILY_SEQUENCE_CODES:
            return super()._create_date_range_seq(date)
        # one range per day instead of per year
        return self.env['ir.sequence.date_range'].sudo().create({
            'date_from': date,
            'date_to': date,
            'sequence_id': self.id,
        })
