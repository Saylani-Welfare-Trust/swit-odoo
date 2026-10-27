from odoo import api, fields, models

# Account the cheque-clearing entry used to credit (hard coded before
# 17.0.1.2.0). Kept for databases upgraded from that version.
LEGACY_CLEARING_ACCOUNT_ID = 6943


class ResCompany(models.Model):
    _inherit = 'res.company'

    pos_cheque_clearing_account_id = fields.Many2one(
        'account.account', string="Cheque Clearing Account",
        help="Credited when treasury clears a POS cheque. Empty: the receivable account the "
             "session closing posted the cheque to.")

    @api.model
    def _bn_set_legacy_cheque_clearing_account(self):
        """On upgrade only: keep the account the clearing entry has always used."""
        module = self.env['ir.module.module'].sudo().search([('name', '=', 'bn_pos_cheque')], limit=1)
        if module.state != 'to upgrade':
            return
        account = self.env['account.account'].sudo().browse(LEGACY_CLEARING_ACCOUNT_ID).exists()
        if not account:
            return
        for company in self.sudo().search([('pos_cheque_clearing_account_id', '=', False)]):
            if account.company_id == company:
                company.pos_cheque_clearing_account_id = account


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_cheque_clearing_account_id = fields.Many2one(
        related='company_id.pos_cheque_clearing_account_id', readonly=False)
