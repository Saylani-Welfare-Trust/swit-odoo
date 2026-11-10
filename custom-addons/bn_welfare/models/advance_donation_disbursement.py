from odoo import models, fields


class AdvanceDonationDisbursementLine(models.Model):
    _inherit = 'advance.donation.disbursement.line'

    welfare_id = fields.Many2one('welfare')
    welfare_line_id = fields.Many2one('welfare.line')

    def _get_donees(self):
        return super()._get_donees() | self.mapped('welfare_line_id.welfare_id.donee_id')

    def _get_source_links(self):
        return [('', rec.name or rec.id) for rec in self.mapped('welfare_id')] + super()._get_source_links()
