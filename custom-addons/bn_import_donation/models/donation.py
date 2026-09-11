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

    GLITCH_NAME = '3 START KK MART'

    def action_fix_glitched_donor_name(self):
        Partner = self.env['res.partner']

        fixed_count = 0
        skipped_count = 0

        for donation in self:
            if not donation.donor_id or donation.donor_id.name != self.GLITCH_NAME:
                skipped_count += 1
                continue

            source_line = self.env['valid.import.donation'].search([
                ('import_donation_id', '=', donation.import_donation_id.id),
                ('transaction_id', '=', donation.transaction_id),
            ], limit=1)

            if not source_line or not source_line.donor_student_name:
                skipped_count += 1
                continue

            correct_name = source_line.donor_student_name

            if correct_name == self.GLITCH_NAME:
                skipped_count += 1
                continue

            partner = Partner.search([('name', '=', correct_name)], limit=1)

            if not partner:
                partner = Partner.create({
                    'name': correct_name,
                    'mobile': source_line.mobile,
                    'cnic_no': source_line.cnic_no,
                    'email': source_line.email,
                })

            donation.donor_id = partner.id
            fixed_count += 1

        if fixed_count == 0:
            raise ValidationError(
                _("No donations were fixed. None of the selected records currently "
                  "show '%s', or no matching import line with a donor name was found. "
                  "%s record(s) were skipped.") % (self.GLITCH_NAME, skipped_count)
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Donor Name Fixed'),
                'message': _('%s donation(s) fixed, %s skipped.') % (fixed_count, skipped_count),
                'type': 'success',
                'sticky': False,
            },
        }