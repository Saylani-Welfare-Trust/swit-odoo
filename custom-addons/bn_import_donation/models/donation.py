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
        if not self:
            raise ValidationError(_("No donation records selected. Please select one or more donations first."))

        Partner = self.env['res.partner']
        donor_category = self.env.ref('bn_profile_management.donor_partner_category')
        donee_category = self.env.ref('bn_profile_management.donee_partner_category')
        individual_category = self.env.ref('bn_profile_management.individual_partner_category')

        linked_count = 0
        created_count = 0
        skipped_count = 0

        for donation in self:
            source_line = self.env['valid.import.donation'].search([
                ('import_donation_id', '=', donation.import_donation_id.id),
                ('transaction_id', '=', donation.transaction_id),
            ], limit=1)

            if not source_line or not source_line.donor_student_name:
                skipped_count += 1
                continue

            name = source_line.donor_student_name

            partner = Partner.search([('name', '=', name)], limit=1)

            if not partner:
                partner = Partner.create({
                    'name': name,
                    'mobile': source_line.mobile,
                    'cnic_no': source_line.cnic_no,
                    'email': source_line.email,
                    'category_id': [(6, 0, [
                        donee_category.id if source_line.is_student else donor_category.id,
                        individual_category.id,
                    ])],
                })
                created_count += 1

            donation.donor_id = partner.id  # overwrite even if already set
            linked_count += 1

        if linked_count == 0:
            raise ValidationError(
                _("No donations could be linked. This usually means no matching "
                "'Valid Import Donation' line was found (missing import_donation_id, "
                "transaction_id, or donor_student_name). %s record(s) were skipped.") % skipped_count
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Donor Synchronization'),
                'message': _(
                    '%s donation(s) linked, %s partner(s) created, %s skipped.'
                ) % (linked_count, created_count, skipped_count),
                'type': 'success',
                'sticky': False,
            },
        }