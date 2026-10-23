from odoo import models, fields, api


type_selection = [
    ('gateway', 'Gateway'),
    ('api', 'API')
]

# Default Donor of the "Web API" gateway before it was configurable.
LEGACY_DEFAULT_DONOR_REGISTRATION = '2025-9999998-9'


class GatewayConfig(models.Model):
    _name = 'gateway.config'
    _description = "Gateway Config"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)

    type = fields.Selection(selection=type_selection, string="Type", tracking=True)

    account_id = fields.Many2one('account.account', string="Debit Account", tracking=True)
    bank_charges_account_id = fields.Many2one(
        'account.account', string="Bank Charges Account", tracking=True,
        help="Expense account for the charges the gateway keeps. The donation income is booked gross, "
             "the gateway account receives the amount after charges.")
    default_partner_id = fields.Many2one(
        'res.partner', string="Default Donor", tracking=True,
        help="Donor used for API donations without a mobile number or email.")

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

    @api.model
    def _bn_setup_gateway_config(self):
        """Data hook (idempotent): settings that used to be hard-coded."""
        self.search([('name', 'in', ('SMIT', 'PIAIC')), ('is_fee', '=', False)]).write({'is_fee': True})
        default_donor = self.env['res.partner'].search(
            [('primary_registration_id', '=', LEGACY_DEFAULT_DONOR_REGISTRATION)], limit=1)
        if default_donor:
            self.search([('type', '=', 'api'), ('default_partner_id', '=', False)]).write(
                {'default_partner_id': default_donor.id})
