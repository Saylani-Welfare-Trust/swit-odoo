from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    advance_donation_journal_id = fields.Many2one(
        'account.journal', string="Advance Donation Journal",
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', id)]",
        help="Bank / cash journal of Advance Donation: the deposit entry of a cheque receipt "
             "and the refund payment of a cancelled amount are posted in it.")

    def _get_advance_donation_journal(self):
        """The configured journal; never a journal found by chance."""
        self.ensure_one()
        journal = self.sudo().advance_donation_journal_id
        if not journal or not journal.active:
            raise UserError(_(
                "Set the Advance Donation Journal of %s first "
                "(Master Setup > Advance Donation > Settings).", self.name))
        return journal

    @api.model
    def _set_default_advance_donation_journal(self):
        """Upgrade / install: keep the journal the code has used so far (the first
        bank journal of the company), so posting goes on as before until it is changed."""
        for company in self.sudo().search([('advance_donation_journal_id', '=', False)]):
            journal = self.env['account.journal'].sudo().search([
                ('type', '=', 'bank'), ('company_id', '=', company.id)], order='sequence, id', limit=1)
            if journal:
                company.advance_donation_journal_id = journal


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    advance_donation_journal_id = fields.Many2one(
        related='company_id.advance_donation_journal_id', readonly=False)
