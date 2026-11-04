import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

collection_point_selection = [
    ('bank', 'Bank'),
    ('branch', 'Branch'),
]

payment_type_selection = [
    ('self', 'Self'),
    ('assigned_officer', 'Assigned Officer (Marfat)'),
]

state_selection = [
    ('draft', 'Draft'),
    ('delivered', 'Delivery Created'),
    ('disbursed', 'Disbursed'),
    ('pending', 'Pending'),
    ('collected', 'Collected'),
    ('return', 'Returned'),
    ('cancel', 'Cancelled'),
]

recurring_duration_selection = [
    (f'{months}_M', f'{months} Months') for months in range(3, 13)
]


class SadqaJariyaLine(models.Model):
    _name = 'sadqa.jariya.line'
    _description = 'Sadqa e Jariya Disbursement Line'

    application_id = fields.Many2one('sadqa.jariya', string='Application', ondelete='cascade')
    donee_id = fields.Many2one(related='application_id.donee_id', string='Donee', store=True)
    order_type = fields.Selection(related='application_id.order_type', string='Order Type', store=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    application_type_id = fields.Many2one('sadqa.jariya.application.type', string='Disbursement Application Type')
    disbursement_category_id = fields.Many2one('sadqa.jariya.disbursement.category', string='Disbursement Category')
    product_id = fields.Many2one('product.product', string='Product')
    product_domain = fields.Char('Product Domain', compute='_compute_product_domain', default="[]", store=True)
    on_hand_qty = fields.Float(string='On Hand Quantity', compute='_compute_on_hand_qty')
    is_hod = fields.Boolean('Is HOD', readonly=True, help="Line added automatically at HOD Approval.")

    employee_category_id_officer = fields.Many2one(
        'hr.employee.category',
        string='Marfat Officer Category',
        default=lambda self: self.env.ref('bn_sadqa_e_jariya.assigned_officer_hr_employee_category', raise_if_not_found=False),
    )
    payment_type = fields.Selection(payment_type_selection, string='Payment Type', default='self')
    assigned_officer_id = fields.Many2one('hr.employee', string='Assigned Officer (Marfat)', domain="[('category_ids', 'in', [employee_category_id_officer])]")
    collection_point = fields.Selection(collection_point_selection, string='Collection Point')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Branch')
    analytic_account_domain = fields.Char('Analytic Account Domain', compute='_compute_analytic_account_domain', default="[]", store=True)
    collection_date = fields.Date('Collection Date', default=fields.Date.context_today)
    recurring_duration = fields.Selection(recurring_duration_selection, string='Recurring Duration')

    quantity = fields.Float('Quantity', default=1.0)
    amount = fields.Float('Amount', related='product_id.list_price', store=True)
    total_amount = fields.Float('Total Amount', compute='_compute_total_amount', store=True, readonly=False)
    manual_total = fields.Boolean(default=False)
    fixed_amount_check = fields.Boolean('Fixed Amount Check', compute='_compute_fixed_amount_check')
    is_cash_category = fields.Boolean('Is Cash Category', compute='_compute_is_cash_category')
    is_collection_point_readonly = fields.Boolean('Is Collection Point Readonly', compute='_compute_is_collection_point_readonly')
    show_deliver_button = fields.Boolean('Show Deliver Button', compute='_compute_show_deliver_button')

    state = fields.Selection(state_selection, string='State', default='draft')
    bill_id = fields.Many2one('account.move', string='Bill', readonly=True)
    return_date = fields.Datetime('Return Date', readonly=True)
    return_bill_id = fields.Many2one('account.move', string='Return Entry', readonly=True)
    return_reason = fields.Text('Return Reason')
    returned_by = fields.Many2one('res.users', string='Returned By', default=lambda self: self.env.user)

    media_ids = fields.Many2many(
        'ir.attachment',
        'sadqa_jariya_line_media_rel',
        'line_id',
        'attachment_id',
        string='Media (Images/Videos)',
    )
    media_count = fields.Integer(compute='_compute_media_count', string='Media Count')

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for rec in self:
            rec.on_hand_qty = rec.product_id.qty_available if rec.product_id else 0.0

    @api.depends('media_ids')
    def _compute_media_count(self):
        for rec in self:
            rec.media_count = len(rec.media_ids)

    @api.depends('application_type_id.product_category_id')
    def _compute_product_domain(self):
        for rec in self:
            product_category = rec.application_type_id.product_category_id
            if not product_category:
                rec.product_domain = "[]"
                continue
            products = self.env['product.product'].search([
                ('categ_id', 'child_of', product_category.id),
                ('product_tmpl_id.is_sadqa_jariya', '=', True),
            ])
            rec.product_domain = str([('id', 'in', products.ids)])

    @api.depends('application_type_id')
    def _compute_analytic_account_domain(self):
        for rec in self:
            branches = rec.application_type_id.analytic_account_ids
            rec.analytic_account_domain = str([('id', 'in', branches.ids)]) if branches else ""

    @api.depends('disbursement_category_id')
    def _compute_fixed_amount_check(self):
        for rec in self:
            rec.fixed_amount_check = rec.disbursement_category_id.name == "In Kind"

    @api.depends('disbursement_category_id')
    def _compute_is_cash_category(self):
        for rec in self:
            rec.is_cash_category = rec.disbursement_category_id.name == "Cash"

    @api.depends('disbursement_category_id')
    def _compute_is_collection_point_readonly(self):
        for rec in self:
            rec.is_collection_point_readonly = rec.disbursement_category_id.name == "In Kind"

    @api.depends('disbursement_category_id', 'state', 'application_id.state', 'application_id.order_type')
    def _compute_show_deliver_button(self):
        for rec in self:
            rec.show_deliver_button = (
                rec.disbursement_category_id.name == 'In Kind'
                and rec.application_id.state == 'approve'
                and rec.application_id.order_type == 'one_time'
                and rec.state not in ['delivered', 'disbursed']
            )

    @api.depends('quantity', 'amount', 'disbursement_category_id')
    def _compute_total_amount(self):
        for rec in self:
            # In Kind total is read-only, so it always follows quantity x price
            if not rec.manual_total or rec.fixed_amount_check:
                rec.total_amount = rec.quantity * rec.amount

    @api.onchange('application_type_id')
    def _onchange_application_type_id(self):
        """Take the category set on the application type"""
        if self.application_type_id.disbursement_category_id:
            self.disbursement_category_id = self.application_type_id.disbursement_category_id

    @api.onchange('disbursement_category_id')
    def _onchange_disbursement_category_id(self):
        """Branch collection for In Kind, quantity is read-only for Cash"""
        if self.disbursement_category_id.name == 'In Kind':
            self.collection_point = 'branch'
        if self.disbursement_category_id.name == 'Cash':
            self.quantity = 1

    def _in_kind_vals(self, vals):
        category = self.env['sadqa.jariya.disbursement.category'].browse(vals.get('disbursement_category_id'))
        if category.name == 'In Kind':
            vals['collection_point'] = 'branch'
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._in_kind_vals(vals) for vals in vals_list])

    def write(self, vals):
        if 'total_amount' in vals:
            vals['manual_total'] = True
        if 'disbursement_category_id' in vals:
            vals = self._in_kind_vals(vals)
        res = super().write(vals)
        if vals.get('state') == 'disbursed':
            self.application_id._auto_disburse_if_all_lines_delivered()
        return res

    @api.model
    def _auto_mark_as_delivered_today(self):
        """Scheduled action: deliveries for approved one-time In Kind lines due by today"""
        lines = self.search([
            ('collection_date', '<=', fields.Date.today()),
            ('state', '=', 'draft'),
            ('disbursement_category_id.name', '=', 'In Kind'),
            ('application_id.state', '=', 'approve'),
            # empty: In Kind lines whose branch was never filled in (read-only for In Kind)
            ('collection_point', 'in', ['branch', False]),
            ('application_id.order_type', '=', 'one_time'),
        ])
        for line in lines:
            try:
                with self.env.cr.savepoint():
                    line.action_delivered()
            except Exception:
                _logger.exception("Could not create delivery for Sadqa e Jariya %s line %s", line.application_id.name, line.id)

    @api.model
    def _auto_create_bills_for_cash_bank(self):
        """Scheduled action: bills for Cash lines collected at the bank on their collection date"""
        lines = self.search([
            ('collection_date', '=', fields.Date.today()),
            ('state', '=', 'draft'),
            ('disbursement_category_id.name', '=', 'Cash'),
            ('collection_point', '=', 'bank'),
            ('bill_id', '=', False),
            ('application_id.state', '=', 'approve'),
            ('application_id.order_type', '=', 'one_time'),
        ])
        for line in lines:
            try:
                with self.env.cr.savepoint():
                    line._create_bill()
                    line.state = 'delivered'
            except Exception:
                _logger.exception("Could not create bill for Sadqa e Jariya line %s", line.id)

    def _create_bill(self):
        """Vendor bill to the donee, paid from Accounting (Cash + Bank collection)"""
        self.ensure_one()
        if not self.application_id.donee_id:
            return
        account = self.product_id.property_account_expense_id or self.product_id.categ_id.property_account_expense_categ_id
        if not account:
            account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        line_vals = {
            'product_id': self.product_id.id,
            'name': self.product_id.name or 'Sadqa e Jariya Payment',
            'quantity': self.quantity,
            # from total_amount, which may have been changed by hand
            'price_unit': self.total_amount / self.quantity if self.quantity else self.total_amount,
            'account_id': account.id,
            # a disbursement, no vendor taxes from the product
            'tax_ids': [(6, 0, [])],
        }
        if self.analytic_account_id:
            line_vals['analytic_distribution'] = {str(self.analytic_account_id.id): 100}
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.application_id.donee_id.id,
            'invoice_date': self.collection_date,
            'date': self.collection_date,
            'ref': self.application_id.name,
            'invoice_line_ids': [(0, 0, line_vals)],
            'sadqa_jariya_line_id': self.id,
        })
        self.bill_id = bill
        bill.action_post()
        return bill

    def action_delivered(self):
        """Delivery to the donee for In Kind lines"""
        for line in self.filtered(lambda l: l.disbursement_category_id.name == 'In Kind'):
            location_src = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
            location_dest = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
            picking = self.env['stock.picking'].create({
                'partner_id': line.application_id.donee_id.id,
                'picking_type_id': self.env.ref('stock.picking_type_out').id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'origin': line.application_id.name,
                'sadqa_jariya_line_id': line.id,
            })
            move = self.env['stock.move'].create({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
            })
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'product_id': line.product_id.id,
                'product_uom_id': line.product_id.uom_id.id,
                'quantity': line.quantity,
                'picking_id': picking.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
            })
            picking.action_assign()
            line.state = 'delivered'

    def action_disbursed(self):
        """Paid: disbursed, or collected by the Assigned Officer (Marfat)"""
        for line in self:
            if line.state not in ['draft', 'delivered']:
                raise ValidationError(_(
                    "This line cannot be paid again. Current state is '%s'. "
                    "Only Draft or Delivery Created lines can be paid."
                ) % line.state)
            line.state = 'collected' if line.payment_type == 'assigned_officer' else 'disbursed'
        self.application_id._auto_disburse_if_all_lines_delivered()
        return True

    def action_cancel_from_pos(self):
        """Cancel the HOD lines the cashier removed from the POS order (lines are never deleted)."""
        lines = self.exists().filtered(lambda l: l.is_hod and l.state == 'draft')
        for application in lines.application_id:
            products = lines.filtered(lambda l: l.application_id == application).product_id
            application.message_post(body=_("HOD line(s) removed at POS by %s: %s") % (
                self.env.user.name, ", ".join(products.mapped('display_name'))
            ))
        lines.write({'state': 'cancel'})
        return True

    def action_mark_pending(self):
        self.write({'state': 'pending'})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def open_disbursement_popup(self):
        self.ensure_one()
        popup = self.env['sadqa.jariya.line.disbursement.popup'].create({
            'line_id': self.id,
            'media_ids': [(6, 0, self.media_ids.ids)],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Disbursement Details'),
            'res_model': 'sadqa.jariya.line.disbursement.popup',
            'res_id': popup.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_return_to_pos(self, **kwargs):
        """Money given to the Assigned Officer (Marfat) comes back to the company"""
        self.ensure_one()
        if self.payment_type != 'assigned_officer':
            raise ValidationError(_("Return is only allowed for 'Assigned Officer (Marfat)' payment type."))
        if self.state != 'pending':
            raise ValidationError(_(
                "Return is only allowed for lines in 'Pending' state. Current state: %s."
            ) % self.state)
        if not self.application_id.donee_id:
            raise ValidationError(_("No donee associated with this line."))

        receipt = self._create_return_receipt()
        self.write({
            'state': 'return',
            'return_date': fields.Datetime.now(),
            'return_bill_id': receipt.id,
            'returned_by': self.env.user.id,
        })
        self.application_id.state = 'return'
        self.application_id.message_post(body=_(
            "💰 Line returned (money received back): %s, %s %s, returned by %s."
        ) % (self.product_id.name, self.total_amount, self.currency_id.symbol, self.env.user.name))
        return True

    def _create_return_receipt(self):
        """Journal entry for the money returned by the donee, cash / bank goes up"""
        cash_account = self.env['account.account'].search([
            ('account_type', 'in', ['asset_cash', 'asset_bank']),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not cash_account:
            raise ValidationError(_("No cash/bank account found to process return."))
        expense_account = self.product_id.property_account_expense_id or self.product_id.categ_id.property_account_expense_categ_id
        if not expense_account:
            expense_account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        journal = self.env['account.journal'].search([
            ('type', 'in', ['cash', 'bank', 'general']),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        donee = self.application_id.donee_id
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"SADQA-RETURN-{self.application_id.name}",
            'line_ids': [
                (0, 0, {
                    'name': f'Return from {donee.name}',
                    'account_id': cash_account.id,
                    'debit': self.total_amount,
                    'credit': 0,
                    'partner_id': donee.id,
                }),
                (0, 0, {
                    'name': f'Sadqa e Jariya Return - {self.product_id.name}',
                    'account_id': expense_account.id,
                    'debit': 0,
                    'credit': self.total_amount,
                    'partner_id': donee.id,
                }),
            ],
        })
        move.action_post()
        return move

    def action_return_to_draft(self):
        """Returned line back to draft, the application back to HOD Approval to be paid again"""
        if self.filtered(lambda l: l.state != 'return'):
            raise ValidationError(_("Only lines in 'Return' state can be moved back to Draft."))
        self.write({'state': 'draft'})
        self.application_id.write({'state': 'hod_approve'})
        return {'type': 'ir.actions.client', 'tag': 'reload'}
