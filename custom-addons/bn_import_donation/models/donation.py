from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

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

    state = fields.Selection(selection=state_selection, string="State", default="draft", tracking=True, index=True)


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('import_donation') or 'New'
        return super().create(vals_list)

    def _check_standalone(self, action):
        for rec in self:
            if rec.import_donation_id:
                raise UserError(_(
                    '"%(donation)s" belongs to the import "%(batch)s": its status follows the import '
                    '(Confirm posts all of its donations).'
                ) % {'donation': rec.display_name, 'batch': rec.import_donation_id.display_name})

    def action_confirm(self):
        self._check_standalone(_('Confirm'))
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('"%s" is already posted.') % rec.display_name)
        self.state = 'posted'

    def action_draft(self):
        self._check_standalone(_('Reset to Draft'))
        for rec in self:
            if rec.state != 'posted':
                raise ValidationError(_('"%s" is already in Draft.') % rec.display_name)
        self.state = 'draft'

    def unlink(self):
        if not self.env.su:
            for rec in self:
                if rec.state == 'posted':
                    raise UserError(_('"%s" is posted and cannot be deleted.') % rec.display_name)
                if rec.import_donation_id:
                    raise UserError(_('Reset the import "%s" to Draft to remove its donations.')
                                    % rec.import_donation_id.display_name)
        return super().unlink()
