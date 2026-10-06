from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class AdvanceDonationWizard(models.TransientModel):
    _name = 'advance.donation.wizard'
    _description = 'Wizard to Select Advance Donation'

    # Dynamic domain field
    advance_donation_domain = fields.Char(
        compute='_compute_advance_donation_domain',
        store=False,
    )
    advance_donation_id = fields.Many2one(
        'advance.donation',
        string="Advance Donation",
        required=True,
        help="Select an advance donation to import its lines."
    )

    product_id = fields.Many2one('product.product', string="Product", required=True)
    today_date = fields.Date(string="Today Date", default=fields.Date.today)

    # Context fields
    welfare_line_id = fields.Many2one('welfare.line', string="Welfare Line")
    recurring_line_id = fields.Many2one('welfare.recurring.line', string="Recurring Line")
    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    livestock_slaughter_id = fields.Many2one(                                     # ← NEW
        'livestock.slaugther', string="Livestock Slaughter")                     # ← NEW

    @api.depends('product_id')
    def _compute_advance_donation_domain(self):
        for rec in self:
            if rec.product_id:
                matching_donations = self.env['advance.donation'].search([
                    ('advance_donation_lines.product_id', '=', rec.product_id.id)
                ])
                rec.advance_donation_domain = str([('id', 'in', matching_donations.ids)])
            else:
                rec.advance_donation_domain = str([('id', 'in', [])])

    def action_show_lines(self):
        if not self.advance_donation_id or not self.product_id:
            raise UserError(_("Please select both Advance Donation and Product."))

        donation_lines = self.advance_donation_id.advance_donation_lines.filtered(
            lambda l: l.product_id.id == self.product_id.id
        )

        if not donation_lines:
            raise UserError(_("No donation lines found for this product."))

        available_lines = donation_lines.filtered(lambda l: not l.is_reserved)
        if not available_lines:
            raise UserError(_("All donation lines for this product are already reserved."))

        # ---------------- Target selection ----------------
        if self.welfare_line_id:
            target_model = self.welfare_line_id
            limit_amount = target_model.total_amount
        elif self.recurring_line_id:
            target_model = self.recurring_line_id
            limit_amount = target_model.amount
        elif self.microfinance_id:
            target_model = self.microfinance_id
            limit_amount = target_model.total_amount
        elif self.livestock_slaughter_id:                                        # ← NEW
            target_model = self.livestock_slaughter_id                           # ← NEW
            limit_amount = target_model.price or 0.0                             # ← NEW
        else:
            raise UserError(_("No target record found to link the donation."))

        if (target_model.advance_donation_id
                and target_model.advance_donation_id.id == self.advance_donation_id.id):
            raise UserError(_("This Advance Donation is already linked to this record."))

        rounding = self.advance_donation_id.currency_id.rounding or 0.01
        is_open_contract = self.advance_donation_id.contract_type == 'open_contract'

        if is_open_contract:
            # An open contract can have one line per day: use the first one that still covers the amount
            donation_amount_to_use = limit_amount
            available_line = available_lines.filtered(
                lambda l: float_compare(l.amount - l.reserved_amount, donation_amount_to_use, precision_rounding=rounding) >= 0
            )[:1]
            if not available_line:
                raise UserError(_("Not enough available amount in the selected donation line."))
        else:
            available_line = available_lines[0]
            # Use available_line.amount instead of paid_amount
            # paid_amount is 0 before payment allocation; amount is the installment value
            # A consolidated line (one per day) holds several products: a record takes one of them
            line_amount = available_line.amount / (available_line.quantity or 1)
            donation_amount_to_use = min(line_amount, available_line.amount - available_line.reserved_amount, limit_amount)

        vals = {
            'advance_donation_id': self.advance_donation_id.id,
            'advance_donation_line_id': available_line.id,
            'advance_donation_amount': donation_amount_to_use,
        }

        # Apply deduction only if recurring_line_id exists
        if self.recurring_line_id:
            current_amount = target_model.amount or 0.0
            vals['amount'] = current_amount - donation_amount_to_use

        target_model.write(vals)

        if is_open_contract:
            available_line.write({
                'reserved_amount': available_line.reserved_amount + donation_amount_to_use
            })
        elif available_line.quantity > 1:
            # Consolidated line: reserved only once all of its amount is used
            reserved_amount = available_line.reserved_amount + donation_amount_to_use
            available_line.write({
                'reserved_amount': reserved_amount,
                'is_reserved': float_compare(reserved_amount, available_line.amount, precision_rounding=rounding) >= 0,
            })
        else:
            available_line.write({'is_reserved': True})

        return {'type': 'ir.actions.act_window_close'}


class AdvanceDonationLineSelectionWizard(models.TransientModel):
    _name = 'advance.donation.line.selection.wizard'
    _description = 'Wizard to Select Specific Donation Line'

    advance_donation_domain = fields.Char(
        compute='_compute_advance_donation_domain',
        store=False,
    )
    advance_donation_id = fields.Many2one('advance.donation', string="Advance Donation", required=True)
    product_id = fields.Many2one('product.product', string="Product", required=True)

    donation_line_ids = fields.One2many(
        'advance.donation.line.wizard',
        'selection_wizard_id',
        string="Available Donation Lines"
    )

    # Context fields (to know where to write back)
    welfare_line_id = fields.Many2one('welfare.line', string="Welfare Line")
    recurring_line_id = fields.Many2one('welfare.recurring.line', string="Recurring Line")
    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    livestock_slaughter_id = fields.Many2one(                                     # ← NEW
        'livestock.slaugther', string="Livestock Slaughter")                     # ← NEW

    @api.depends('product_id')
    def _compute_advance_donation_domain(self):
        for rec in self:
            if rec.product_id:
                matching_donations = self.env['advance.donation'].search([
                    ('advance_donation_lines.product_id', '=', rec.product_id.id)
                ])
                rec.advance_donation_domain = str([('id', 'in', matching_donations.ids)])
            else:
                rec.advance_donation_domain = str([('id', 'in', [])])

    def action_confirm(self):
        """Confirm selected donation line"""
        selected_line = self.donation_line_ids.filtered(lambda l: l.is_selected)

        if not selected_line:
            raise UserError(_("Please select a donation line."))

        if len(selected_line) > 1:
            raise UserError(_("You can only select one donation line."))

        selected_line = selected_line[0]

        if selected_line.is_reserved:
            raise UserError(_("This donation line is already reserved."))

        # -------- Target selection --------
        if self.welfare_line_id:
            target_model = self.welfare_line_id
        elif self.recurring_line_id:
            target_model = self.recurring_line_id
        elif self.microfinance_id:
            target_model = self.microfinance_id
        elif self.livestock_slaughter_id:                                        # ← NEW
            target_model = self.livestock_slaughter_id                           # ← NEW
        else:
            raise UserError(_("No target record found to link the donation."))

        vals = {
            'advance_donation_id': self.advance_donation_id.id,
            'advance_donation_line_id': selected_line.original_line_id.id,
            'advance_donation_amount': selected_line.paid_amount,
        }

        # Apply deduction only if recurring_line_id exists
        if self.recurring_line_id:
            current_amount = target_model.amount or 0.0
            vals['amount'] = current_amount - selected_line.paid_amount

        target_model.write(vals)

        # Mark original line as reserved
        selected_line.original_line_id.write({'is_reserved': True})

        return {'type': 'ir.actions.act_window_close'}


class AdvanceDonationLineWizard(models.TransientModel):
    _name = 'advance.donation.line.wizard'
    _description = 'Wizard Lines for Donation Selection'

    selection_wizard_id = fields.Many2one(
        'advance.donation.line.selection.wizard',
        string="Selection Wizard",
        required=True,
        ondelete='cascade'
    )

    original_line_id = fields.Many2one(
        'advance.donation.lines',
        string="Original Donation Line",
    )

    product_id = fields.Many2one('product.product', string="Product")
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id')
    is_reserved = fields.Boolean(string="Reserved", readonly=True)
    is_selected = fields.Boolean(string="Select")
    currency_id = fields.Many2one(
        'res.currency', 'Currency',
        default=lambda self: self.env.company.currency_id
    )