from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

PRESCRIPTION_STATES = [
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('billed', 'Billed'),
    ('cancel', 'Cancelled'),
]


class MedicalPrescription(models.Model):
    """Products approved for a patient at the prescription desk, billed at the billing counter"""
    _name = 'medical.prescription'
    _description = 'Medical Prescription'
    _inherit = ['mail.thread', 'pos.link.mixin']
    _order = 'id desc'

    name = fields.Char(
        'Prescription No.', required=True, readonly=True, copy=False, index='trigram',
        default=lambda self: _('New'))
    partner_id = fields.Many2one(
        'res.partner', 'Patient', required=True, index=True, tracking=True,
        domain="[('category_id.name', '=', 'Donee'), ('category_id.name', '=', 'Medical'), ('state', '=', 'register')]")
    registration_id = fields.Char(related='partner_id.primary_registration_id', string='Registration No.')
    cnic_no = fields.Char(related='partner_id.cnic_no', string='CNIC No.')
    mobile = fields.Char(related='partner_id.mobile', string='Mobile No.')
    doctor_name = fields.Char('Doctor', tracking=True)
    note = fields.Text('Remarks')

    line_ids = fields.One2many('medical.prescription.line', 'prescription_id', 'Products', copy=True)
    amount_total = fields.Monetary('Total', compute='_compute_amount_total', store=True)
    company_id = fields.Many2one(
        'res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')

    state = fields.Selection(
        PRESCRIPTION_STATES, 'Status', required=True, default='draft', index=True, copy=False, tracking=True)
    approved_by_id = fields.Many2one('res.users', 'Approved By', readonly=True, copy=False)
    approved_date = fields.Datetime('Approved On', readonly=True, copy=False)
    desk_config_id = fields.Many2one('pos.config', 'Prescription Desk', readonly=True, copy=False)
    # the bill (pos.link.mixin: with its session, POS and cashier once paid;
    # before that the prescription desk's session where it was approved)
    pos_order_id = fields.Many2one('pos.order', 'Bill', readonly=True, copy=False, index='btree_not_null')
    billed_date = fields.Datetime('Billed On', readonly=True, copy=False)
    billing_config_id = fields.Many2one(related='pos_order_id.config_id', string='Billing Counter')

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for prescription in self:
            prescription.amount_total = sum(prescription.line_ids.mapped('price_subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.prescription') or _('New')
        return super().create(vals_list)

    def unlink(self):
        if any(prescription.state != 'draft' for prescription in self):
            raise UserError(_("Only draft prescriptions can be deleted; cancel the others."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def action_approve(self):
        for prescription in self:
            if prescription.state != 'draft':
                raise UserError(_("Only draft prescriptions can be approved."))
            if not prescription.line_ids:
                raise UserError(_("Add the prescribed products to %s before approving it.", prescription.name))
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })

    def action_cancel(self):
        if any(prescription.state == 'billed' for prescription in self):
            raise UserError(_("A billed prescription can't be cancelled; refund its bill instead."))
        self.write({'state': 'cancel'})

    def action_draft(self):
        if any(prescription.state != 'cancel' for prescription in self):
            raise UserError(_("Only cancelled prescriptions can be reset to draft."))
        self.write({'state': 'draft', 'approved_by_id': False, 'approved_date': False})

    def _mark_billed(self, pos_order):
        """Called when the bill of the prescription is paid at the billing counter"""
        states = dict(PRESCRIPTION_STATES)
        for prescription in self:
            if prescription.state == 'approved':
                prescription.write({
                    'state': 'billed',
                    'pos_order_id': pos_order.id,
                    'pos_session_id': pos_order.session_id.id,
                    'pos_config_id': pos_order.config_id.id,
                    'pos_reference': pos_order.pos_reference,
                    'pos_cashier_id': pos_order.user_id.id,
                    'billed_date': fields.Datetime.now(),
                })
                prescription._note_bill_differences(pos_order)
            else:
                # the POS checks this before the payment, but a paid order must still be recorded
                prescription.message_post(body=_(
                    "Billed again on %(order)s while the prescription was %(state)s.",
                    order=pos_order.name, state=states[prescription.state],
                ))

    def action_open_patient(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Patient'), 'res_model': 'mh.patient',
            'res_id': self.partner_id.id, 'view_mode': 'form', 'views': [(False, 'form')],
        }

    def action_open_bill(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Bill'), 'res_model': 'pos.order',
            'res_id': self.pos_order_id.id, 'view_mode': 'form', 'views': [(False, 'form')],
        }

    def _note_bill_differences(self, pos_order):
        """The billing counter can still change the order: what was billed
        differently from the prescription is written in its chatter."""
        self.ensure_one()
        prescribed = {}
        for line in self.line_ids:
            prescribed[line.product_id] = prescribed.get(line.product_id, 0.0) + line.qty
        billed = {}
        for line in pos_order.lines:
            billed[line.product_id] = billed.get(line.product_id, 0.0) + line.qty
        differences = []
        for product in set(prescribed) | set(billed):
            if round(prescribed.get(product, 0.0) - billed.get(product, 0.0), 4):
                differences.append(_('%(product)s: prescribed %(prescribed)s, billed %(billed)s') % {
                    'product': product.display_name, 'prescribed': prescribed.get(product, 0.0),
                    'billed': billed.get(product, 0.0)})
        if differences:
            self.message_post(body=Markup('%s<br/>%s') % (
                _('Billed on %s differently from the prescription:') % pos_order.name,
                Markup('<br/>').join(differences)))
        return differences

    # ------------------------------------------------------------------
    # POS
    # ------------------------------------------------------------------

    def _pos_data(self, session):
        """Prescriptions as the POS shows and bills them (patient in the POS partner format)"""
        partners = {partner['id']: partner for partner in session._mh_patient_pos_data(self.partner_id)}
        result = []
        for prescription in self:
            approved_date = prescription.approved_date and fields.Datetime.context_timestamp(
                prescription, prescription.approved_date)
            result.append({
                'id': prescription.id,
                'name': prescription.name,
                'state': prescription.state,
                'doctor_name': prescription.doctor_name or '',
                'note': prescription.note or '',
                'amount_total': prescription.amount_total,
                'approved_date': approved_date.strftime('%d-%m-%Y %H:%M') if approved_date else '',
                'approved_by': prescription.approved_by_id.name or '',
                'desk': prescription.desk_config_id.name or '',
                'partner': partners.get(prescription.partner_id.id),
                'lines': [{
                    'id': line.id,
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.display_name,
                    'qty': line.qty,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'price_subtotal': line.price_subtotal,
                    'note': line.note or '',
                } for line in prescription.line_ids],
            })
        return result


class MedicalPrescriptionLine(models.Model):
    _name = 'medical.prescription.line'
    _description = 'Medical Prescription Line'
    _order = 'prescription_id, sequence, id'

    prescription_id = fields.Many2one(
        'medical.prescription', 'Prescription', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', 'Product', required=True, domain="[('sale_ok', '=', True)]")
    qty = fields.Float('Quantity', required=True, default=1.0, digits='Product Unit of Measure')
    price_unit = fields.Float('Unit Price', digits='Product Price')
    discount = fields.Float('Discount (%)', digits='Discount')
    price_subtotal = fields.Monetary('Subtotal', compute='_compute_price_subtotal', store=True)
    note = fields.Char('Instructions', help="Printed in the remarks of the bill, e.g. the dosage")
    state = fields.Selection(related='prescription_id.state')
    company_id = fields.Many2one(related='prescription_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='prescription_id.currency_id')

    _sql_constraints = [
        ('qty_positive', 'CHECK(qty > 0)', 'The prescribed quantity must be positive.'),
    ]

    @api.depends('qty', 'price_unit', 'discount')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.qty * line.price_unit * (1 - (line.discount or 0.0) / 100.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.lst_price

    @api.constrains('discount', 'price_unit')
    def _check_price(self):
        for line in self:
            if not 0 <= line.discount <= 100:
                raise ValidationError(_("The discount must be between 0 and 100%."))
            if line.price_unit < 0:
                raise ValidationError(_("The unit price can't be negative."))
