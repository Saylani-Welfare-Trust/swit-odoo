from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

state_selection = [
    ('draft', 'Draft'),
    ('posted', 'Posted')
]


class Donation(models.Model):
    _name = 'donation'
    _description = "Donation"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    donor_id = fields.Many2one('res.partner', string="Donor / Student", tracking=True)
    journal_id = fields.Many2one('account.journal', string="Journal", tracking=True)
    product_id = fields.Many2one('product.product', string="Product", tracking=True)
    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config", tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id.id)
    currency_id = fields.Many2one(related='company_id.currency_id', string="Currency")
    import_donation_id = fields.Many2one('import.donation', string="Import Donation")

    name = fields.Char('Name', default="New", tracking=True)
    transaction_id = fields.Char('Transaction ID', tracking=True)

    reference = fields.Text('Reference/Remarks', tracking=True)
    
    date = fields.Char('Date', tracking=True)

    amount = fields.Monetary('Amount', tracking=True)

    is_fee = fields.Boolean('Is Fee', tracking=True)

    state = fields.Selection(selection=state_selection, string="State", default="draft", tracking=True)


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('import_donation') or ('New')

        return super(Donation, self).create(vals)
    
    def action_confirm(self):
        self.state = 'posted'
    
    def action_draft(self):
        self.state = 'draft'



    def action_sync_existing_donors(self):
        donation = self[0] if self else None
        if not donation:
            return

        txn_id = (donation.transaction_id or '').strip()

        valid_line = self.env['valid.import.donation'].search([
            ('transaction_id', '=', txn_id)
        ], limit=1)

        invalid_line = self.env['invalid.import.donation'].search([
            ('transaction_id', '=', txn_id)
        ], limit=1)

        all_valid_count = self.env['valid.import.donation'].search_count([])

        raise ValidationError(
            _("Debug: donation.transaction_id=%r (len=%s) | "
              "valid_line=%s donor_name=%r | "
              "invalid_line=%s reason=%r | "
              "total valid lines in system=%s") %
            (txn_id, len(txn_id),
             valid_line.id if valid_line else False,
             valid_line.donor_student_name if valid_line else None,
             invalid_line.id if invalid_line else False,
             invalid_line.reason if invalid_line else None,
             all_valid_count)
        )