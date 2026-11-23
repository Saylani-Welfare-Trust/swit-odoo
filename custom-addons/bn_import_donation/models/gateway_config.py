from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.bn_profile_management.models.partner_tag_domain import tag_domain


type_selection = [
    ('gateway', 'Gateway'),
    ('api', 'API')
]

# Donor of the donations received without a donor number (mobile / CNIC),
# unless the gateway configuration names another one.
LEGACY_DEFAULT_DONOR_REGISTRATION = '2025-9999998-9'


class GatewayConfig(models.Model):
    _name = 'gateway.config'
    _description = "Gateway Config"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)

    type = fields.Selection(selection=type_selection, string="Type", tracking=True)

    journal_id = fields.Many2one(
        'account.journal', string="Journal", tracking=True, domain=[('type', 'in', ('bank', 'cash'))],
        help="Journal of the entry created when an import of this gateway is confirmed (required to post).")
    account_id = fields.Many2one('account.account', string="Debit Account", tracking=True)
    product_id = fields.Many2one(
        'product.product', string="Fee Product", tracking=True,
        help="Student fees only: every line of the file is booked on this product, whatever its Course. "
             "Empty: the Course is mapped to a product by the configuration lines.")
    bank_charges_account_id = fields.Many2one(
        'account.account', string="Bank Charges Account", tracking=True,
        help="Expense account for the charges the gateway keeps. The donation income is booked gross, "
             "the gateway account receives the amount after charges.")
    difference_account_id = fields.Many2one(
        'account.account', string="Difference Account", tracking=True,
        domain="[('deprecated', '=', False)]",
        help="Where the difference between the debit and the credit of a donation entry is parked "
             "(rounding of amounts with more decimals than the currency), so the entry always balances.")
    default_partner_id = fields.Many2one(
        'res.partner', string="Default Donor", tracking=True, domain=tag_domain('donor'),
        help="Donor of the donations received without a donor number (no mobile and no CNIC). "
             "Empty: the donor with Primary Registration ID %s." % LEGACY_DEFAULT_DONOR_REGISTRATION)

    is_fee = fields.Boolean(
        'Student Fees', tracking=True,
        help="The file contains student fees (SMIT, PIAIC ...): the Course column is used as the product "
             "and the payers are tagged as students.")

    gateway_config_line_ids = fields.One2many('gateway.config.line', 'gateway_config_id', string="Gateway Config Lines")
    gateway_config_header_ids = fields.One2many('gateway.config.header', 'gateway_config_id', string="Gateway Config Headers")
    gateway_config_currency_ids = fields.One2many('gateway.config.currency', 'gateway_config_id', string="Gateway Config Currencies")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The Bank Name must be unique!')
    ]

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id.default_account_id:
            self.account_id = self.journal_id.default_account_id

    def _balance_entry_lines(self, line_vals, currency, label):
        """Make the (0, 0, vals) entry lines balance: each amount rounded to the
        currency, and a remaining difference parked on the Difference Account.
        Returns the lines (a new list)."""
        lines = []
        for command in line_vals:
            vals = dict(command[2])
            vals['debit'] = currency.round(vals.get('debit') or 0.0)
            vals['credit'] = currency.round(vals.get('credit') or 0.0)
            lines.append((0, 0, vals))
        diff = currency.round(sum(l[2]['debit'] for l in lines) - sum(l[2]['credit'] for l in lines))
        if currency.is_zero(diff):
            return lines
        if not self.difference_account_id:
            raise UserError(_(
                'The entry of %(label)s is off by %(diff)s (rounding): set the Difference Account on the '
                'gateway configuration "%(gateway)s" to park it.') % {
                'label': label, 'diff': diff, 'gateway': self.display_name or '-'})
        lines.append((0, 0, {
            'account_id': self.difference_account_id.id,
            'name': _('Difference (rounding) - %s') % label,
            'debit': -diff if diff < 0 else 0.0,
            'credit': diff if diff > 0 else 0.0,
        }))
        return lines

    def _get_journal(self, company):
        self.ensure_one()
        # the gateway's own journal only, never a journal found by chance
        journal = self.journal_id
        if journal and journal.company_id != company:
            return self.env['account.journal']
        return journal

    def _get_product(self, name):
        """Product of a file line: the Fee Product of a student fees file,
        else the product mapped to the line's Product / Course."""
        self.ensure_one()
        if self.is_fee and self.product_id:
            return self.product_id
        return self._get_product_line(name).product_id

    def _get_product_line(self, *names):
        """Mapping line of the first of ``names`` that is configured (case and
        surrounding spaces ignored)."""
        self.ensure_one()
        lines = {(line.name or '').strip().lower(): line for line in self.gateway_config_line_ids if line.name}
        for name in names:
            line = lines.get((name or '').strip().lower())
            if line:
                return line
        return self.env['gateway.config.line']

    def _get_default_donor(self):
        """Donor of a donation received without a donor number: the gateway's
        Default Donor, else the donor with Primary Registration ID
        2025-9999998-9."""
        partner = self[:1].default_partner_id
        if not partner:
            partner = self.env['res.partner'].sudo().with_context(active_test=False).search(
                [('primary_registration_id', '=', LEGACY_DEFAULT_DONOR_REGISTRATION)], limit=1)
        return partner.sudo(False)

    @api.model
    def _setup_gateway_config(self):
        """Data hook (idempotent): settings that used to be hard-coded."""
        self.search([('name', 'in', ('SMIT', 'PIAIC')), ('is_fee', '=', False)]).write({'is_fee': True})
        default_donor = self.env['res.partner'].search(
            [('primary_registration_id', '=', LEGACY_DEFAULT_DONOR_REGISTRATION)], limit=1)
        if default_donor:
            self.search([('default_partner_id', '=', False)]).write(
                {'default_partner_id': default_donor.id})
        # gateways without a journal used the company's first bank journal:
        # that journal is now set on them, and can be changed there
        journal = self.env['account.journal'].sudo().search(
            [('type', '=', 'bank'), ('company_id', '=', self.env.company.id)], order='sequence, id', limit=1)
        if journal:
            self.search([('journal_id', '=', False)]).write({'journal_id': journal.id})
