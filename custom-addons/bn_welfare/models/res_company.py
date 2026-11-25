from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    welfare_return_journal_id = fields.Many2one(
        'account.journal', string="Welfare Return Journal",
        domain="[('type', 'in', ('cash', 'bank')), ('company_id', '=', id)]",
        help="Cash / bank journal of the money a donee returns (Assigned Officer payments).")

    def _get_welfare_return_journal(self):
        """The configured journal; never a journal found by chance."""
        self.ensure_one()
        journal = self.sudo().welfare_return_journal_id
        if not journal or not journal.active:
            raise UserError(_(
                "Set the Welfare Return Journal of %s first (Master Setup > Welfare > Settings).", self.name))
        return journal

    @api.model
    def _set_default_welfare_return_journal_id(self):
        """Upgrade / install: keep the journal the code has used so far (the first
        cash journal of the company) until it is changed."""
        for company in self.sudo().search([('welfare_return_journal_id', '=', False)]):
            journal = self.env['account.journal'].sudo().search([
                ('type', '=', 'cash'), ('company_id', '=', company.id)], order='sequence, id', limit=1)
            if journal:
                company.welfare_return_journal_id = journal


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    welfare_return_journal_id = fields.Many2one(related='company_id.welfare_return_journal_id', readonly=False)
