from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    medical_equipment_journal_id = fields.Many2one(
        'account.journal', string="Medical Equipment Journal",
        domain="[('type', 'in', ('general',)), ('company_id', '=', id)]",
        help="Journal of the entry made when a security deposit is donated.")

    def _get_medical_equipment_journal(self):
        """The configured journal; never a journal found by chance."""
        self.ensure_one()
        journal = self.sudo().medical_equipment_journal_id
        if not journal or not journal.active:
            raise UserError(_(
                "Set the Medical Equipment Journal of %s first (Master Setup > Medical Equipment Settings).", self.name))
        return journal

    @api.model
    def _set_default_medical_equipment_journal_id(self):
        """Upgrade / install: keep the journal the code has used so far (the first
        general journal of the company) until it is changed."""
        for company in self.sudo().search([('medical_equipment_journal_id', '=', False)]):
            journal = self.env['account.journal'].sudo().search([
                ('type', '=', 'general'), ('company_id', '=', company.id)], order='sequence, id', limit=1)
            if journal:
                company.medical_equipment_journal_id = journal


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    medical_equipment_journal_id = fields.Many2one(related='company_id.medical_equipment_journal_id', readonly=False)
