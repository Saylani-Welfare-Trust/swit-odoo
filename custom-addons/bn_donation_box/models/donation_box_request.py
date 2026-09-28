# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

status_selection = [
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]

APPROVE_GROUP = 'bn_donation_box.donation_box_request_approve_reject_group'


class DonationBoxRequest(models.Model):
    _name = 'donation.box.request'
    _description = "Donation Box Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "bn.workflow.mixin"]
    _order = 'id desc'
    _bn_guarded_fields = ('status',)

    rider_id = fields.Many2one('hr.employee', string="Installer", tracking=True)

    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company, index=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string="Warehouse", tracking=True,
        default=lambda self: self._default_warehouse_id(),
        domain="[('company_id', '=', company_id)]")

    picking_id = fields.Many2one('stock.picking', string="Picking", tracking=True, copy=False)
    picking_type_id = fields.Many2one(
        'stock.picking.type', string="Operation Type", tracking=True,
        default=lambda self: self._default_picking_type_id(),
        domain="['|', ('warehouse_id', '=', warehouse_id), ('warehouse_id', '=', False)]",
        help="Defaults to the Donation Box operation type configured on the warehouse.")
    source_location_id = fields.Many2one(
        'stock.location', string="Source Location",
        compute='_compute_locations', store=True)
    destination_location_id = fields.Many2one(
        'stock.location', string="Destination Location",
        compute='_compute_locations', store=True)

    employee_category_id = fields.Many2one(
        'hr.employee.category', string="Employee Category",
        default=lambda self: self._default_employee_category_id())

    name = fields.Char('Name', default="New", copy=False)

    request_date = fields.Datetime(string='Request Date', default=fields.Datetime.now, tracking=True)

    status = fields.Selection(selection=status_selection, string='Status', default='draft',
                              tracking=True, copy=False)

    key_tag_assign = fields.Boolean('Key Tag Assign', default=False, copy=False)

    donation_box_request_line_ids = fields.One2many(
        'donation.box.request.line', 'donation_box_request_id', string='Donation Request Line')
    donation_box_registration_installation_ids = fields.One2many(
        'donation.box.registration.installation', 'donation_box_request_id',
        string='Donation Box Registration/Installation')

    # ------------------------------------------------------------------
    # Defaults / computes
    # ------------------------------------------------------------------
    @api.model
    def _default_employee_category_id(self):
        category = self.env.ref('bn_donation_box.installer_hr_employee_category', raise_if_not_found=False)
        return category.id if category else False

    @api.model
    def _default_warehouse_id(self):
        Warehouse = self.env['stock.warehouse']
        company = self.env.company
        user = self.env.user
        allowed = Warehouse
        if 'allowed_warehouse_ids' in user._fields:
            allowed = user.allowed_warehouse_ids.filtered(lambda w: w.company_id == company)
        warehouse = allowed[:1] or Warehouse.search([('company_id', '=', company.id)], limit=1)
        return warehouse.id

    @api.model
    def _default_picking_type_id(self):
        warehouse = self.env['stock.warehouse'].browse(self._default_warehouse_id())
        picking_type = warehouse.donation_box_picking_type_id
        if not picking_type:
            # Backward compatibility: the historical global Donation Box operation type.
            picking_type = self.env.ref('bn_donation_box.donation_box_stock_picking_type',
                                        raise_if_not_found=False)
        return picking_type.id if picking_type else False

    @api.depends('picking_type_id', 'picking_type_id.default_location_src_id',
                 'picking_type_id.default_location_dest_id')
    def _compute_locations(self):
        for request in self:
            request.source_location_id = request.picking_type_id.default_location_src_id
            request.destination_location_id = request.picking_type_id.default_location_dest_id

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        picking_type = self.warehouse_id.donation_box_picking_type_id
        if picking_type:
            self.picking_type_id = picking_type

    @api.constrains('picking_type_id', 'warehouse_id')
    def _check_picking_type_warehouse(self):
        for request in self:
            picking_type = request.picking_type_id
            if picking_type.warehouse_id and request.warehouse_id and picking_type.warehouse_id != request.warehouse_id:
                raise ValidationError(_(
                    'The operation type "%(type)s" does not belong to warehouse "%(warehouse)s".'
                ) % {'type': picking_type.display_name, 'warehouse': request.warehouse_id.display_name})

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('donation_box_request') or 'New'
        return super().create(vals_list)

    def unlink(self):
        for request in self:
            if request.status == 'approved':
                raise UserError(_(
                    'Request "%s" is approved and already moved stock; it cannot be deleted.'
                ) % request.display_name)
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_reject(self):
        self._bn_require_group(APPROVE_GROUP)
        self._bn_check_state('status', ('draft',), _('Reject'))
        self._bn_write({'status': 'rejected'})
        return True

    def check_lines(self):
        """Duplicate boxes inside the same request."""
        for request in self:
            lot_ids = request.donation_box_request_line_ids.filtered(
                lambda l: not l.is_returned).mapped('lot_id.id')
            if len(lot_ids) != len(set(lot_ids)):
                raise ValidationError(_('Duplicate Box No. found in request lines.'))

    def _bn_validate_before_approve(self):
        self.ensure_one()
        if not self.rider_id:
            raise ValidationError(_('Please select the Installer before approving the request.'))
        if not self.picking_type_id:
            raise ValidationError(_(
                'No Donation Box operation type is configured. Configure it on the warehouse '
                '(Inventory > Configuration > Warehouses > Donation Box Operation Type) '
                'or select it on the request.'))
        if not self.source_location_id or not self.destination_location_id:
            raise ValidationError(_(
                'The operation type "%s" has no default source/destination location.'
            ) % self.picking_type_id.display_name)

        lines = self.donation_box_request_line_ids
        if not lines:
            raise ValidationError(_('Please add at least one box line before approving the request.'))

        self.check_lines()
        lines._bn_validate_for_approval()

    def action_approve(self):
        self._bn_require_group(APPROVE_GROUP)
        self._bn_check_state('status', ('draft',), _('Approve'))
        for request in self:
            request._bn_validate_before_approve()
            request._bn_do_approve()
        return True

    def _bn_do_approve(self):
        self.ensure_one()
        lines = self.donation_box_request_line_ids

        # 1. Stock first: it is the step most likely to fail, and everything below
        #    runs in the same transaction so a failure rolls the whole approval back.
        picking = self._bn_create_and_validate_picking()

        # 2. Key tags (only once per request).
        if not self.key_tag_assign:
            lines._bn_prefix_key_tags()

        # 3. One registration (+ key, through the hook of bn_key_management) per box.
        for line in lines:
            registration = self.env['donation.box.registration.installation'].create({
                'donation_box_request_id': self.id,
                'lot_id': line.lot_id.id,
                'lock_no': line.lock_no,
                'product_id': line.product_id.id,
                'installer_id': self.rider_id.id,
                'old_box_no': line.old_box_no,
            })
            registration._bn_key_create(line)

        # 4. The boxes are now consumed.
        lines.mapped('lot_id').write({'lot_consume': True})

        self._bn_write({
            'status': 'approved',
            'picking_id': picking.id,
            'key_tag_assign': True,
        })

    def generate_records(self):
        """Kept for backward compatibility. The approval now does this itself."""
        raise UserError(_('Records are generated automatically when the request is approved.'))

    # ------------------------------------------------------------------
    # Stock helpers
    # ------------------------------------------------------------------
    def _bn_create_and_validate_picking(self):
        self.ensure_one()
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        MoveLine = self.env['stock.move.line']

        picking = Picking.create({
            'picking_type_id': self.picking_type_id.id,
            'location_id': self.source_location_id.id,
            'location_dest_id': self.destination_location_id.id,
            'origin': self.name,
        })

        # One move (with its own move line and serial) per box.
        for line in self.donation_box_request_line_ids:
            move = Move.create({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': 1.0,
                'product_uom': line.product_id.uom_id.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
                'picking_id': picking.id,
                'company_id': picking.company_id.id,
            })
            MoveLine.create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom_id': line.product_id.uom_id.id,
                'quantity': 1.0,
                'lot_id': line.lot_id.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
            })

        picking.action_confirm()
        self._bn_validate_picking(picking)
        return picking

    @api.model
    def _bn_validate_picking(self, picking):
        """Validate ``picking`` and make sure it really is done.

        ``button_validate`` may return a wizard action (backorder, immediate transfer ...)
        instead of validating; ignoring that silently leaves stock untouched while the
        Donation Box records claim otherwise.
        """
        picking.with_context(skip_backorder=True, skip_immediate=True).button_validate()
        if picking.state != 'done':
            raise UserError(_(
                'The stock transfer %(picking)s could not be validated automatically '
                '(status: %(state)s). Nothing has been changed.'
            ) % {'picking': picking.display_name, 'state': picking.state})
        return picking

    @api.model
    def _bn_return_lot(self, picking, lot):
        """Create and validate a return of ONE box (``lot``) of the done ``picking``.

        The move line is created with the exact serial before the transfer is
        confirmed, so the return can never pick another box of the same product
        that happens to sit in the same location.
        """
        source_line = picking.move_line_ids.filtered(lambda ml: ml.lot_id == lot)[:1]
        if not source_line:
            raise ValidationError(_('Box "%(lot)s" does not belong to transfer %(picking)s.') % {
                'lot': lot.display_name, 'picking': picking.display_name})
        source_move = source_line.move_id
        product = source_line.product_id

        picking_type = picking.picking_type_id.return_picking_type_id or picking.picking_type_id
        return_picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking.location_dest_id.id,
            'location_dest_id': picking.location_id.id,
            'origin': _('Return of %s') % picking.name,
        })
        return_move = self.env['stock.move'].create({
            'name': _('Return: %s') % product.display_name,
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'product_uom': source_line.product_uom_id.id,
            'location_id': picking.location_dest_id.id,
            'location_dest_id': picking.location_id.id,
            'picking_id': return_picking.id,
            'origin_returned_move_id': source_move.id,
            'company_id': return_picking.company_id.id,
        })
        self.env['stock.move.line'].create({
            'move_id': return_move.id,
            'picking_id': return_picking.id,
            'product_id': product.id,
            'product_uom_id': source_line.product_uom_id.id,
            'quantity': 1.0,
            'lot_id': lot.id,
            'location_id': picking.location_dest_id.id,
            'location_dest_id': picking.location_id.id,
        })
        return_picking.action_confirm()
        self._bn_validate_picking(return_picking)
        return return_picking

    @api.model
    def _bn_find_done_picking(self, request):
        """The done transfer created when ``request`` was approved."""
        picking = request.picking_id
        if not picking or picking.state != 'done':
            picking = self.env['stock.picking'].search([
                ('origin', '=', request.name),
                ('state', '=', 'done'),
            ], order='id desc', limit=1)
        return picking
