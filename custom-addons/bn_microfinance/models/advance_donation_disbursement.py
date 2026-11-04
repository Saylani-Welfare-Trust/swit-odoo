from odoo import models, fields


class AdvanceDonationDisbursementLine(models.Model):
    _inherit = 'advance.donation.disbursement.line'

    microfinance_id = fields.Many2one('microfinance')

    def _get_donees(self):
        return super()._get_donees() | self.mapped('microfinance_id.donee_id')

    def _get_source_links(self):
        return super()._get_source_links() + [
            ('Microfinance', rec.display_name or rec.id) for rec in self.mapped('microfinance_id')
        ]
