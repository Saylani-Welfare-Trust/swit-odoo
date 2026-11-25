from odoo import models, fields, _, api
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo.addons.bn_profile_management.models.partner_tag_domain import tag_domain


state_selection = [
    ('not_received', 'Draft'),
    ('slaughtered', 'Slaughtered'),
    ('cutting', 'Cutting'),
    ('material_request', 'Material Request'),
    ('done', 'Done')
]


class LivestockSlaughter(models.Model):
    _name = 'livestock.slaugther'
    _description = "Livestock Slaugther"
    _inherit = ["mail.thread", "mail.activity.mixin", 'pos.link.mixin']


    donee_id = fields.Many2one('res.partner', string="Donee", domain=tag_domain('donee'))
    product_id = fields.Many2one('product.product', string="Product")
    pos_order_id = fields.Many2one('pos.order', string="POS Order", copy=False, index=True)
    pos_order_line_id = fields.Many2one('pos.order.line', string="POS Order Line", copy=False, index=True)
    direct_deposit_line_id = fields.Many2one('direct.deposit.line', string="Direct Deposit Line", copy=False, index=True)
    donation_id = fields.Many2one('donation', string="Import Donation", copy=False, index=True)
    api_donation_item_id = fields.Many2one('api.donation.item', string="API Donation Item", copy=False, index=True)
    cutting_material_id = fields.Many2one('livestock.cutting.material', string='Cutting Record', copy=False)
    cutting_line_ids = fields.One2many(
        related='cutting_material_id.livestock_cutting_material_line_ids',
        string='Cutting Lines',
        readonly=True,
    )
    material_request_id = fields.Many2one('livestock.cutting.material', string='Material Request', copy=False)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
    transfer_location = fields.Many2one('stock.location', string='Destination Location')
    source_location_id = fields.Many2one('stock.location', string='Source Location')
    # where Slaughtered puts the animal: a location marked "Is Slaughter Location",
    # or for the Meat / Goat / Chicken departments "Is Meat / Goat / Chicken Location"
    slaughter_location_id = fields.Many2one(
        'stock.location', string='Slaughter Location', copy=False,
        domain="[('id', 'in', slaughter_location_option_ids)]",
        help="Where the animal was slaughtered: its Destination Location when Slaughtered "
             "(a location marked Is Slaughter Location).")
    slaughter_location_option_ids = fields.Many2many(
        'stock.location', string='Slaughter Location Options', compute='_compute_location_options')
    # where Cutting puts the animal: a location marked "Is Cutting Location"
    cutting_location_id = fields.Many2one(
        'stock.location', string='Cutting Location', copy=False,
        domain="[('is_cutting_location', '=', True)]",
        help="Where Cutting puts the animal (a location marked Is Cutting Location). "
             "Filled when the warehouse has only one.")
    transfer_picking_id = fields.Many2one('stock.picking', string='Transfer', copy=False, readonly=True)
    transfer_remarks = fields.Text('Transfer Remarks', copy=False)
    truck_number = fields.Char('Truck Number', copy=False, readonly=True)
    # Order Transfer (Draft lines): the animal is brought from this location into the POS location
    order_transfer_location_id = fields.Many2one('stock.location', string='Order Transfer Location', copy=False, readonly=True)
    order_transfer_picking_id = fields.Many2one('stock.picking', string='Order Transfer', copy=False, readonly=True)

    name = fields.Char('Name', default='New')
    code = fields.Char(related='product_id.default_code', string="Product Code", store=True)
    ref = fields.Char('Source Document')

    quantity = fields.Integer('Quantity', default=1)

    price = fields.Monetary('Price', currency_field='currency_id', default=0)

    state = fields.Selection(selection=state_selection, string="State", default='not_received')
    start_time = fields.Datetime('Start Time')
    end_time = fields.Datetime('End Time')

    is_meat_depart = fields.Boolean('Is Meat Department')
    is_goat_depart = fields.Boolean('Is Goat Department')
    is_chicken_depart = fields.Boolean('Is Chicken Department')
    confirm_hide = fields.Boolean('Confirm Hide')
    cutting_hide = fields.Boolean('Cutting Hide')
    transfer_bool = fields.Boolean('Hide Transferred')

    # One record per animal: a source line (POS line, Direct Deposit line,
    # donation, API item) gets as many records as animals it paid for, see
    # _create_for_source. The former one-record-per-line unique constraints
    # are dropped by data/upgrade_hooks.xml.

    @api.model
    def _drop_line_unique_constraints(self):
        for name in ('unique_pos_order_line_id', 'unique_direct_deposit_line_id',
                     'unique_donation_id', 'unique_api_donation_item_id'):
            self.env.cr.execute('ALTER TABLE livestock_slaugther DROP CONSTRAINT IF EXISTS %s'
                                % ('livestock_slaugther_' + name))

    @api.model
    def _create_for_source(self, source_field, source, animals, total, vals):
        """Create the missing records of ``source`` (one per animal, ``animals``
        in all, sharing ``total``). Run again, it creates nothing more."""
        animals = int(animals or 0)
        if animals <= 0:
            return self.browse()
        existing = self.sudo().search_count([(source_field, '=', source.id)])
        missing = animals - existing
        if missing <= 0:
            return self.browse()
        currency = self.env.company.currency_id
        total = total or 0.0
        per_animal = currency.round(total / animals)
        vals = dict(vals, **{source_field: source.id, 'quantity': 1})
        # the last animal takes the rounding difference, so the records add up to the total
        return self.sudo().create([
            dict(vals, price=per_animal if index < animals - 1
                 else currency.round(total - per_animal * (animals - 1)))
            for index in range(existing, animals)])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                if vals.get('is_meat_depart'):
                    vals['name'] = self.env['ir.sequence'].next_by_code('meat_department') or ('New')
                elif vals.get('is_chicken_depart'):
                    vals['name'] = self.env['ir.sequence'].next_by_code('chicken_department') or ('New')
                elif vals.get('is_goat_depart'):
                    vals['name'] = self.env['ir.sequence'].next_by_code('goat_department') or ('New')
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('livestock_slaugther') or ('New')
        records = super().create(vals_list)
        for record in records.filtered(lambda r: not r.source_location_id):
            location = record._pos_source_location()
            if location:
                record.sudo().source_location_id = location.id
        records._init_destination()
        records._fill_default_locations()
        return records

    def _init_destination(self):
        """Source Location: the POS location the line came from (a line not from
        a POS: where it waits for slaughter in its warehouse). The Destination
        Location starts the same and changes with the Bulk Transfer; users see
        the lines whose Destination Location has one of their analytic accounts."""
        for record in self.sudo():
            source = record.source_location_id
            if not source:
                try:
                    source = record._slaughter_source_location()
                except UserError:  # no warehouse to wait in
                    continue
                record.source_location_id = source
            if source and not record.transfer_location:
                record.transfer_location = source

    def _slaughter_role(self):
        """The location role the animal's Slaughtered destination must have."""
        self.ensure_one()
        return ('is_meat_location' if self.is_meat_depart else 'is_goat_location' if self.is_goat_depart
                else 'is_chicken_location' if self.is_chicken_depart else 'is_slaughter_location')

    @api.depends('is_meat_depart', 'is_goat_depart', 'is_chicken_depart')
    def _compute_location_options(self):
        Location = self.env['stock.location']
        for record in self:
            record.slaughter_location_option_ids = Location._role_locations(record._slaughter_role())

    @api.onchange('slaughter_location_id')
    def _onchange_slaughter_location_id(self):
        if self.slaughter_location_id and (not self.cutting_location_id or
                                           self.cutting_location_id.warehouse_id != self.slaughter_location_id.warehouse_id):
            self.cutting_location_id = self.env['stock.location']._single_role_location(
                'is_cutting_location', self.slaughter_location_id.warehouse_id)

    def _fill_default_locations(self):
        """Empty locations get their warehouse's only one of that role (several:
        the user chooses on the record)."""
        Location = self.env['stock.location']
        for record in self.sudo():
            # (the Slaughter Location is the Destination Location when Slaughtered)
            if not record.cutting_location_id and record.state in ('not_received', 'slaughtered') \
                    and not record.transfer_bool:
                warehouse = (record.slaughter_location_id or record.transfer_location).warehouse_id
                record.cutting_location_id = Location._single_role_location('is_cutting_location', warehouse)

    def _pos_source_location(self):
        """The stock location of the POS the order was created at (empty for
        a record that does not come from a POS). Read as superuser: livestock
        users do not need access to the POS configuration."""
        self.ensure_one()
        record = self.sudo()
        config = record.pos_order_id.config_id or record.pos_session_id.config_id or record.pos_config_id
        return config.picking_type_id.default_location_src_id.with_env(self.env)

    def _livestock_warehouse(self):
        """The warehouse the animal is handled in: of its slaughter location,
        else of the POS it was sold at, else of its Branch / Site (else the user's)."""
        self.ensure_one()
        record = self.sudo()
        if record.slaughter_location_id.warehouse_id:
            return record.slaughter_location_id.warehouse_id.sudo(False)
        return self.env['stock.warehouse']._warehouse_for(
            self._pos_source_location() or record.source_location_id or None, branch=self.node_id)

    def _department_location(self):
        """Where Slaughtered puts the animal: its Slaughter Location (for a
        department animal, its Meat / Goat / Chicken location)."""
        self.ensure_one()
        if not self.slaughter_location_id:
            raise ValidationError(_("Choose the Slaughter Location of %s.") % self.name)
        role = self._slaughter_role()
        if not self.slaughter_location_id[role]:
            raise ValidationError(_("%(location)s is not marked %(role)s (%(record)s).",
                                    location=self.slaughter_location_id.display_name,
                                    role=self.env['stock.location']._fields[role].string, record=self.name))
        return self.slaughter_location_id

    def _slaughtered_location(self):
        """Where the animal is now: the destination of its Slaughtered transfer
        (records slaughtered before the per-warehouse locations included),
        else its department location."""
        self.ensure_one()
        # (its Order Transfer, made before, and Bulk Transfer, made after, are not that transfer)
        picking = self.env['stock.picking'].sudo().search([
            ('source_record_ref', '=', '%s,%s' % (self._name, self.id)), ('state', '=', 'done'),
            ('id', 'not in', (self.order_transfer_picking_id | self.transfer_picking_id).ids),
            ('location_dest_id.usage', 'in', ('internal', 'transit'))], order='id', limit=1)
        return picking.location_dest_id.sudo(False) or self._department_location()

    def _slaughter_source_location(self):
        """Where the animal waits for slaughter, and where Order Transfer brings it:
        the location of the POS it was sold at, else the livestock operation
        type's source location in its own warehouse."""
        self.ensure_one()
        return self._pos_source_location() or self.env['stock.warehouse']._get_program_type(
            'livestock', branch=self.node_id, location=self._livestock_warehouse().lot_stock_id
        ).default_location_src_id

    def _check_transfer_ready(self, bulk):
        """Order Transfer: Draft lines not order transferred yet.
        Bulk Transfer: Slaughtered lines not bulk transferred yet."""
        if not self:
            raise ValidationError(_("Please select the records to transfer."))
        state_labels = dict(self._fields['state']._description_selection(self.env))
        not_ready = []
        for rec in self:
            if bulk and rec.transfer_bool:
                reason = _('already bulk transferred')
            elif not bulk and rec.order_transfer_picking_id:
                reason = _('already order transferred')
            elif rec.state != ('slaughtered' if bulk else 'not_received'):
                reason = state_labels.get(rec.state, rec.state)
            else:
                continue
            not_ready.append('%s - %s (%s)' % (rec.name, rec.product_id.display_name, reason))
        if not_ready:
            message = (_("Bulk Transfer is only for Slaughtered lines that are not bulk transferred yet.") if bulk
                       else _("Order Transfer is only for Draft lines that are not order transferred yet."))
            raise ValidationError(
                _("%s Remove these lines from your selection:\n%s") % (message, "\n".join(not_ready))
            )

    def action_confirm(self):
        self.ensure_one()
        
        if not self.env.user.has_group('bn_livestock_slaugther.livestock_slaugther_user_group'):
            raise AccessError(_("You do not have the access rights to confirm Livestock Slaughter records."))
        
        if self.state != 'not_received':
            return
        # slaughtered where it is: its Destination Location, a slaughter location
        location = self.transfer_location
        if not location.is_slaughter_location:
            raise ValidationError(_(
                "%(record)s can only be slaughtered at a location marked \"Is Slaughter Location\": "
                "its Destination Location %(location)s is not one. Order Transfer it to a slaughter location first.",
                record=self.name, location=location.display_name or _('(none)')))
        self.slaughter_location_id = location
        source_location = self._slaughter_source_location()
        picking_type = self.env['stock.warehouse']._get_program_type(
            'livestock', source_location, branch=self.node_id)

        # Retrieve the product based on the product code
        product = self.product_id
        if not product:
            raise ValidationError(f"Product with code '{self.code}' not found.")

        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': location.id,
            'origin': self.name or 'Live Stock Slaughter',
            'source_record_ref': '%s,%s' % (self._name, self.id),
        })

        # Create the stock move
        self.env['stock.move'].create({
            'name': product.display_name,
            'product_id': product.id,
            'product_uom_qty': self.quantity,
            'quantity': self.quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })

        # Confirm and assign the picking
        picking.action_confirm()
        picking.action_assign()

        # Set the done quantities and validate the picking
        for move_line in picking.move_line_ids:
            move_line.quantity = move_line.quantity_product_uom
        picking.button_validate()

        self.confirm_hide = True
        self.state = 'slaughtered'

    def action_cutting(self):
        self.ensure_one()
        if self.state != 'slaughtered':
            raise ValidationError("Cutting can only be started after the animal is slaughtered.")
        if self.transfer_bool:
            raise ValidationError(_("%s was sent away by Bulk Transfer: it cannot be cut here.") % self.name)
        if not self.product_id:
            raise ValidationError("Please select a product before starting cutting.")
        self._check_cutting_bom()

        # from the source location (the POS location the animal was sold at) into the Cutting location
        source_location = self._slaughter_source_location()
        if not self.cutting_location_id:
            self._fill_default_locations()
        if not self.cutting_location_id:
            raise ValidationError(_("Choose the Cutting Location of %s.") % self.name)
        location = self.cutting_location_id
        picking_type = self.env['stock.warehouse']._get_program_type(
            'livestock', source_location, branch=self.node_id)

        product = self.product_id

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': location.id,
            'origin': self.name or '',
            'source_record_ref': '%s,%s' % (self._name, self.id),
        })

        self.env['stock.move'].create({
            'name': product.display_name,
            'product_id': product.id,
            'product_uom_qty': self.quantity,
            'quantity': self.quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })

        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()

        # the material request is made with the cutting, from the product's BOM
        self.state = 'material_request'
        self.cutting_hide = True
        material_request = self._create_material_request()
        self.cutting_material_id = material_request.id
        # the Destination Location becomes the Cutting Location: written last, as the
        # line may then belong to another Branch / Site than the user's
        self.transfer_location = location

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.cutting.material',
            'res_id': material_request.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _check_cutting_bom(self):
        """Cutting makes the material request from the product's BOM: lines whose
        product has no BOM (with component products) are refused before anything moves."""
        Material = self.env['livestock.cutting.material']
        missing = self.filtered(
            lambda r: not Material._bom_for_product(r.product_id).bom_line_ids.filtered('product_id'))
        if missing:
            raise ValidationError(
                _("No BOM with component products found for: %s. Create the BOM of the product "
                  "(or of its product template) first.")
                % ', '.join(sorted(set(missing.mapped('product_id.display_name')))))

    def _create_material_request(self):
        """The material request of the cut animal: the components of its product's BOM."""
        self.ensure_one()
        material_request = self.material_request_id
        if not material_request:
            material_request = self.env['livestock.cutting.material'].create({
                'product_id': self.product_id.id,
                'quantity': self.quantity,
                'price': self.price,
                'code': self.code,
                'state': 'not_received',
                'livestock_slaughter_id': self.id,
                'cutting_location_id': self.cutting_location_id.id,
            })
            self.material_request_id = material_request.id
        if not material_request._get_product_bom():
            raise ValidationError(
                "No BOM found for %s. Create the BOM for this exact product or its product template."
                % self.product_id.display_name
            )
        material_request._populate_bom_lines(self)
        if not material_request.livestock_cutting_material_line_ids:
            raise ValidationError(
                "The BOM for %s has no component products. Add BOM lines first."
                % self.product_id.display_name
            )
        return material_request

    def action_bulk_cutting(self):
        """List header: start Cutting for all the selected Slaughtered lines."""
        if not self:
            raise ValidationError(_("Please select the records to cut."))
        state_labels = dict(self._fields['state']._description_selection(self.env))
        not_ready = []
        for rec in self:
            if rec.transfer_bool:
                reason = _('already bulk transferred')
            elif rec.state != 'slaughtered':
                reason = state_labels.get(rec.state, rec.state)
            else:
                continue
            not_ready.append('%s - %s (%s)' % (rec.name, rec.product_id.display_name, reason))
        if not_ready:
            raise ValidationError(
                _("Bulk Cutting is only for Slaughtered lines that are not bulk transferred. "
                  "Remove these lines from your selection:\n%s") % "\n".join(not_ready))
        self._fill_default_locations()
        no_location = self.filtered(lambda r: not r.cutting_location_id)
        if no_location:
            raise ValidationError(_("Choose the Cutting Location of: %s") % ', '.join(no_location.mapped('name')))
        self._check_cutting_bom()
        # (after its cutting a line may belong to another Branch / Site: not read again)
        request_ids = [rec.action_cutting()['res_id'] for rec in self]
        return {
            'name': _('Cutting'),
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.cutting.material',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', request_ids)],
            'target': 'current',
        }

    def action_material_request(self):
        """Lines cut before the material request was made with the cutting."""
        self.ensure_one()
        if self.state != 'cutting':
            raise ValidationError("Material Request can only be opened during cutting.")
        if not self.product_id:
            raise ValidationError("Please select a product before opening the material request.")
        material_request = self._create_material_request()
        self.state = 'material_request'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.cutting.material',
            'res_id': material_request.id,
            'view_mode': 'form',
            'target': 'current',
        }

    
    def action_open_wizard(self):
        """Form: Order Transfer of this Draft line"""
        
        self.ensure_one()
        self._check_transfer_ready(bulk=False)

        return {
            'name': _('Order Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.slaugther.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_livestock_slaughter_id': self.id},
        }

    def action_open_order_transfer(self):
        """List header: bring the selected Draft lines into their POS location (Send)"""
        self._check_transfer_ready(bulk=False)
        if len(self) == 1:
            return self.action_open_wizard()

        return {
            'name': _('Order Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.slaugther.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_livestock_slaughter_ids': [(6, 0, self.ids)]},
        }

    def action_open_bulk_transfer(self):
        """List header: send the selected Slaughtered lines out of their POS location and print the slip"""
        self._check_transfer_ready(bulk=True)

        return {
            'name': _('Bulk Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.slaugther.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_livestock_slaughter_ids': [(6, 0, self.ids)],
                'default_is_bulk': True,
            },
        }

    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for line in self:
            line.on_hand_qty = line.product_id.qty_available if line.product_id else 0.0