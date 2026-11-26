from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.addons.bn_profile_management.models.partner_tag_domain import tag_domain
from odoo.exceptions import AccessError, UserError, ValidationError

PRESCRIPTION_STATES = [
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('billed', 'Billed'),
    ('cancel', 'Cancelled'),
]

MEDICAL_USER = 'bn_medical_pos.group_medical_user'
MEDICAL_DOCTOR = 'bn_medical_pos.group_medical_doctor'
MEDICAL_MANAGER = 'bn_medical_pos.group_medical_manager'
# changed by the workflow buttons and the POS only
WORKFLOW_FIELDS = {
    'state', 'approved_by_id', 'approved_date', 'desk_config_id', 'intake_order_id', 'pos_order_id', 'billed_date',
    'pos_session_id', 'pos_config_id', 'pos_reference', 'pos_cashier_id',
}
# fixed by the paid till: only an administrator corrects them
TILL_FIELDS = {'partner_id', 'doctor_id', 'category_product_ids', 'company_id'}
# what is worked on while the prescription is a draft
DRAFT_FIELDS = {'line_ids', 'note', 'doctor_name', 'location_id'}


class MedicalPrescription(models.Model):
    """Made by the paid till of a patient, filled and approved by the doctor's side, then billed at the counter"""
    _name = 'medical.prescription'
    _description = 'Medical Prescription'
    _inherit = ['mail.thread', 'pos.link.mixin']
    _order = 'id desc'

    name = fields.Char(
        'Prescription No.', required=True, readonly=True, copy=False, index='trigram',
        default=lambda self: _('New'))
    partner_id = fields.Many2one(
        'res.partner', 'Patient', required=True, index=True, tracking=True,
        domain=tag_domain('donee', 'patient', registered=True))
    registration_id = fields.Char(related='partner_id.primary_registration_id', string='Registration No.')
    cnic_no = fields.Char(related='partner_id.cnic_no', string='CNIC No.')
    mobile = fields.Char(related='partner_id.mobile', string='Mobile No.')
    doctor_id = fields.Many2one('medical.doctor', 'Doctor', index=True, tracking=True, ondelete='restrict')
    doctor_name = fields.Char('Doctor (old)', tracking=True, help="Doctor typed on prescriptions made before the doctors list")
    category_product_ids = fields.Many2many(
        'product.product', 'medical_prescription_category_product_rel', 'prescription_id', 'product_id', 'Category',
        help="The product(s) selected and paid at the counter")
    # shown as text: the user's Allowed Categories may not include the paid product
    category_name = fields.Char('Category', compute='_compute_category_name', store=True, compute_sudo=True)
    intake_order_id = fields.Many2one('pos.order', 'Till', readonly=True, copy=False, index='btree_not_null')
    # chosen by the doctor (the counter's stock location by default): the on hand quantities and the stock check use it
    location_id = fields.Many2one(
        'stock.location', 'Location', tracking=True, domain="[('usage', '=', 'internal')]",
        help="Where the products are given from: the On Hand quantities and the stock check of Prescribed use it.")
    # for the views: a doctor has no rights on the POS orders
    has_till = fields.Boolean(compute='_compute_has_till', compute_sudo=True)
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
    desk_config_id = fields.Many2one('pos.config', 'Counter', readonly=True, copy=False)
    # the bill (pos.link.mixin: with its session, POS and cashier once paid;
    # before that the session of its till)
    pos_order_id = fields.Many2one('pos.order', 'Bill', readonly=True, copy=False, index='btree_not_null')
    billed_date = fields.Datetime('Billed On', readonly=True, copy=False)
    billing_config_id = fields.Many2one(related='pos_order_id.config_id', string='Billing Counter')

    @api.depends('intake_order_id')
    def _compute_has_till(self):
        for prescription in self:
            prescription.has_till = bool(prescription.intake_order_id)

    @api.depends('category_product_ids')
    def _compute_category_name(self):
        for prescription in self:
            prescription.category_name = ', '.join(prescription.category_product_ids.mapped('display_name')) or False

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for prescription in self:
            prescription.amount_total = sum(prescription.line_ids.mapped('price_subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                # the local date of the user (the counter), not the server's UTC date: restarts at local midnight
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'medical.prescription', sequence_date=fields.Date.context_today(self)) or _('New')
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            if WORKFLOW_FIELDS & set(vals):
                raise AccessError(_("The status of a prescription only changes with its buttons."))
            if TILL_FIELDS & set(vals) and not self.env.user.has_group(MEDICAL_MANAGER):
                raise AccessError(_("The patient, doctor and category come from the paid till."))
            if DRAFT_FIELDS & set(vals) and any(prescription.state != 'draft' for prescription in self):
                raise UserError(_("Only a draft prescription can be changed."))
        return super().write(vals)

    def unlink(self):
        if any(prescription.state != 'draft' for prescription in self):
            raise UserError(_("Only draft prescriptions can be deleted; cancel the others."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    @api.model
    def _create_from_till(self, pos_order, note=False):
        """The paid till of the first phase makes the draft prescription (once, an order can be synced again)"""
        return self.search([('intake_order_id', '=', pos_order.id)], limit=1) or self.create({
            'partner_id': pos_order.partner_id.id,
            'doctor_id': pos_order.medical_doctor_id.id,
            'category_product_ids': [(6, 0, pos_order.lines.product_id.ids)],
            'note': (note or '').strip() or False,
            'company_id': pos_order.company_id.id,
            'desk_config_id': pos_order.config_id.id,
            'location_id': pos_order.config_id.picking_type_id.default_location_src_id.id,
            'intake_order_id': pos_order.id,
            'pos_session_id': pos_order.session_id.id,
            'pos_config_id': pos_order.config_id.id,
            # no pos_reference: pos.link.mixin would take the till for the bill of the prescription
            'pos_cashier_id': pos_order.user_id.id,
        })

    def _stock_products(self, products):
        """The products with their on hand quantity at the prescription's location, else the counter's
        stock location (anywhere in the company when there is neither)"""
        self.ensure_one()
        location = self.location_id or self.desk_config_id.picking_type_id.default_location_src_id
        context = {'location': location.id, 'compute_child': True} if location else {}
        return products.with_company(self.company_id).with_context(**context)

    def _check_on_hand(self):
        """Stock-tracked products must be on hand at the counter's location"""
        for prescription in self.sudo():
            products = prescription.line_ids.product_id.filtered(lambda p: p.detailed_type == 'product')
            empty = prescription._stock_products(products).filtered(lambda p: p.qty_available <= 0)
            if empty:
                raise UserError(_(
                    "%(name)s can't be marked Prescribed: no stock on hand at %(location)s for\n%(products)s",
                    name=prescription.name,
                    location=(prescription.location_id or prescription.desk_config_id.picking_type_id.default_location_src_id).display_name or _('the company'),
                    products='\n'.join('- %s (on hand: %s)' % (p.display_name, p.qty_available) for p in empty),
                ))

    def action_approve(self):
        # the button is the group's: also refused over RPC, and only on the user's doctors (record rules)
        if not self.env.su:
            if not any(self.env.user.has_group(group) for group in (MEDICAL_USER, MEDICAL_DOCTOR)):
                raise AccessError(_('You are not allowed to do this action.'))
            self.check_access_rights('write')
            self.check_access_rule('write')
        for prescription in self:
            if prescription.state != 'draft':
                raise UserError(_("Only draft prescriptions can be approved."))
            if not prescription.line_ids:
                raise UserError(_("Add the prescribed products to %s before approving it.", prescription.name))
        self._check_on_hand()
        self.sudo().write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })

    def action_cancel(self):
        # the button is the group's: also refused over RPC
        if not self.env.su and not any(self.env.user.has_group(group) for group in ('bn_medical_pos.group_medical_manager',)):
            raise AccessError(_('You are not allowed to do this action.'))
        if any(prescription.state == 'billed' for prescription in self):
            raise UserError(_("A billed prescription can't be cancelled; refund its bill instead."))
        self.sudo().write({'state': 'cancel'})

    def action_draft(self):
        # the button is the group's: also refused over RPC
        if not self.env.su and not any(self.env.user.has_group(group) for group in ('bn_medical_pos.group_medical_manager',)):
            raise AccessError(_('You are not allowed to do this action.'))
        if any(prescription.state != 'cancel' for prescription in self):
            raise UserError(_("Only cancelled prescriptions can be reset to draft."))
        self.sudo().write({'state': 'draft', 'approved_by_id': False, 'approved_date': False})

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

    def action_open_till(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Till'), 'res_model': 'pos.order',
            'res_id': self.intake_order_id.id, 'view_mode': 'form', 'views': [(False, 'form')],
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
                'doctor_name': prescription.doctor_id.name or prescription.doctor_name or '',
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
        'product.product', 'Product', required=True,
        domain="[('sale_ok', '=', True), ('available_in_pos', '=', True), ('pos_categ_ids.mh_prescription_scope', '=', True)]",
        help="Products of the categories with Prescription switched on in Medical & Health > Configuration > Categories.")
    qty = fields.Float('Quantity', required=True, default=1.0, digits='Product Unit of Measure')
    price_unit = fields.Float('Unit Price', digits='Product Price')
    discount = fields.Float('Discount (%)', digits='Discount')
    price_subtotal = fields.Monetary('Subtotal', compute='_compute_price_subtotal', store=True)
    note = fields.Char('Instructions', help="Printed in the remarks of the bill, e.g. the dosage")
    state = fields.Selection(related='prescription_id.state')
    company_id = fields.Many2one(related='prescription_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='prescription_id.currency_id')
    can_edit_price = fields.Boolean(compute='_compute_can_edit_price')
    # as superuser: a doctor has no stock rights
    is_storable = fields.Boolean(compute='_compute_qty_on_hand', compute_sudo=True)
    qty_on_hand = fields.Float(
        'On Hand', compute='_compute_qty_on_hand', compute_sudo=True, digits='Product Unit of Measure',
        help="On hand at the stock location of the counter of the prescription")

    _sql_constraints = [
        ('qty_positive', 'CHECK(qty > 0)', 'The prescribed quantity must be positive.'),
    ]

    @api.depends('product_id', 'prescription_id.location_id', 'prescription_id.desk_config_id', 'prescription_id.company_id')
    def _compute_qty_on_hand(self):
        for prescription in self.prescription_id:
            lines = self.filtered(lambda line: line.prescription_id == prescription)
            stock = prescription._stock_products(lines.product_id.filtered(lambda p: p.detailed_type == 'product'))
            on_hand = {product.id: product.qty_available for product in stock}
            for line in lines:
                line.is_storable = line.product_id.id in on_hand
                line.qty_on_hand = on_hand.get(line.product_id.id, 0.0)
        orphans = self.filtered(lambda line: not line.prescription_id)
        orphans.is_storable = False
        orphans.qty_on_hand = 0.0

    @api.depends_context('uid')
    def _compute_can_edit_price(self):
        can_edit = self.env.su or self.env.user.has_group(MEDICAL_MANAGER)
        for line in self:
            line.can_edit_price = can_edit

    def _keeps_list_price(self):
        """Doctors and users add products at their sales price, only an administrator changes it"""
        return not self.env.su and not self.env.user.has_group(MEDICAL_MANAGER)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            prescriptions = self.env['medical.prescription'].browse(
                {vals['prescription_id'] for vals in vals_list if vals.get('prescription_id')})
            if any(prescription.state != 'draft' for prescription in prescriptions):
                raise UserError(_("Only a draft prescription can be changed."))
        if self._keeps_list_price():
            for vals in vals_list:
                vals['price_unit'] = self.env['product.product'].sudo().browse(vals['product_id']).lst_price
                vals['discount'] = 0
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and any(line.prescription_id.state != 'draft' for line in self):
            raise UserError(_("Only a draft prescription can be changed."))
        if self._keeps_list_price():
            vals = {key: value for key, value in vals.items() if key not in ('price_unit', 'discount')}
            if vals.get('product_id'):
                vals.update(price_unit=self.env['product.product'].sudo().browse(vals['product_id']).lst_price, discount=0)
        return super().write(vals)

    def unlink(self):
        if not self.env.su and any(line.prescription_id.state != 'draft' for line in self):
            raise UserError(_("Only a draft prescription can be changed."))
        return super().unlink()

    @api.depends('qty', 'price_unit', 'discount')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.qty * line.price_unit * (1 - (line.discount or 0.0) / 100.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.lst_price

    @api.constrains('product_id')
    def _check_product_allowed_in_pos(self):
        # as superuser: the user's Allowed Categories don't change what the counter can sell
        for line in self.sudo():
            product = line.product_id
            if not (product.sale_ok and product.available_in_pos
                    and any(product.pos_categ_ids.mapped('mh_prescription_scope'))):
                raise ValidationError(_(
                    "%s can't be prescribed: Prescription isn't switched on for its category in "
                    "Medical & Health > Configuration > Categories.", product.display_name))

    @api.constrains('discount', 'price_unit')
    def _check_price(self):
        for line in self:
            if not 0 <= line.discount <= 100:
                raise ValidationError(_("The discount must be between 0 and 100%."))
            if line.price_unit < 0:
                raise ValidationError(_("The unit price can't be negative."))
