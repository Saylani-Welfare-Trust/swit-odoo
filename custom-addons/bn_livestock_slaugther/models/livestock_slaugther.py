from odoo import models, fields, _, api
from odoo.exceptions import ValidationError, AccessError
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
    transfer_picking_id = fields.Many2one('stock.picking', string='Transfer', copy=False, readonly=True)
    transfer_remarks = fields.Text('Transfer Remarks', copy=False)
    truck_number = fields.Char('Truck Number', copy=False, readonly=True)

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
        return records

    def _pos_source_location(self):
        """The stock location of the POS the order was created at (empty for
        a record that does not come from a POS). Read as superuser: livestock
        users do not need access to the POS configuration."""
        self.ensure_one()
        record = self.sudo()
        config = record.pos_order_id.config_id or record.pos_session_id.config_id or record.pos_config_id
        return config.picking_type_id.default_location_src_id.with_env(self.env)

    def _check_order_transfer(self):
        """Only slaughtered lines that are not transferred yet can be transferred."""
        if not self:
            raise ValidationError(_("Please select the records to transfer."))
        transferred = self.filtered('transfer_bool')
        if transferred:
            raise ValidationError(
                _("These records are already transferred:\n%s")
                % "\n".join(transferred.mapped(lambda r: '%s - %s' % (r.name, r.product_id.display_name)))
            )
        not_slaughtered = self.filtered(lambda r: r.state != 'slaughtered')
        if not_slaughtered:
            raise ValidationError(
                _("Only slaughtered records can be transferred:\n%s")
                % "\n".join(not_slaughtered.mapped(lambda r: '%s - %s' % (r.name, r.product_id.display_name)))
            )

    def action_confirm(self):
        self.ensure_one()
        
        if not self.env.user.has_group('bn_livestock_slaugther.livestock_slaugther_user_group'):
            raise AccessError(_("You do not have the access rights to confirm Livestock Slaughter records."))
        
        if self.state != 'not_received':
            return
        # Retrieve the 'Slaughter Stock' location
        location = None

        if self.is_meat_depart:
            location = self.env['stock.location'].search([('name', '=', 'Meat')], limit=1)
        elif self.is_goat_depart:
            location = self.env['stock.location'].search([('name', '=', 'Goat')], limit=1)
        elif self.is_chicken_depart:
            location = self.env['stock.location'].search([('name', '=', 'Chicken')], limit=1)
        else:
            location = self.env['stock.location'].search([('name', '=', 'Slaughter Stock')], limit=1)
        
        if not location:
            raise ValidationError("Slaughter Stock, Meat or Chicken or Goat location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type of the POS warehouse
        source_location = self._pos_source_location()
        picking_type = self.env['stock.warehouse']._get_program_type('livestock', source_location)
        if not picking_type:
            raise ValidationError("Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")
        source_location = source_location or picking_type.default_location_src_id

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
        if not self.product_id:
            raise ValidationError("Please select a product before starting cutting.")

        location = self.env['stock.location'].search([('name', '=', 'Livestock Cutting')], limit=1)
        if not location:
            raise ValidationError("Livestock Cutting location not found. Please create it in Inventory > Configuration > Locations.")

        source_location = self._pos_source_location()
        picking_type = self.env['stock.warehouse']._get_program_type('livestock', source_location)
        if not picking_type:
            raise ValidationError("Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")
        source_location = source_location or picking_type.default_location_src_id

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

        self.start_time = fields.Datetime.now()
        self.state = 'cutting'
        self.cutting_hide = True

        cutting_record = self.cutting_material_id
        if not cutting_record:
            cutting_record = self.env['livestock.cutting.material'].create({
                'product_id': self.product_id.id,
                'quantity': self.quantity,
                'price': self.price,
                'code': self.code,
                'state': 'received',
                'start_time': self.start_time,
                'livestock_slaughter_id': self.id,
            })
            self.cutting_material_id = cutting_record.id
        else:
            cutting_record.write({
                'livestock_cutting_material_line_ids': [(5, 0, 0)],
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.cutting.material',
            'res_id': cutting_record.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_material_request(self):
        self.ensure_one()
        if self.state != 'cutting':
            raise ValidationError("Material Request can only be opened during cutting.")
        if not self.product_id:
            raise ValidationError("Please select a product before opening the material request.")

        material_request = self.material_request_id
        if material_request == self.cutting_material_id:
            material_request = self.env['livestock.cutting.material']
        if not material_request:
            material_request = self.env['livestock.cutting.material'].create({
                'product_id': self.product_id.id,
                'quantity': self.quantity,
                'price': self.price,
                'code': self.code,
                'state': 'not_received',
                'livestock_slaughter_id': self.id,
            })
            self.material_request_id = material_request.id
        bom = material_request._get_product_bom()
        if not bom:
            material_request.unlink()
            raise ValidationError(
                "No BOM found for %s. Create the BOM for this exact product or its product template."
                % self.product_id.display_name
            )

        material_request._populate_bom_lines(self)
        if not material_request.livestock_cutting_material_line_ids:
            material_request.unlink()
            raise ValidationError(
                "The BOM for %s has no component products. Add BOM lines first."
                % self.product_id.display_name
            )

        self.state = 'material_request'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.cutting.material',
            'res_id': material_request.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_end_cutting(self):
        self.ensure_one()
        if self.state != 'material_request':
            raise ValidationError("End Cutting is available only after creating the material request.")
        if not self.product_id:
            raise ValidationError("Please select a product before ending cutting.")
        if not self.material_request_id:
            self.action_material_request()
        elif not self.material_request_id.livestock_cutting_material_line_ids:
            self.material_request_id._populate_bom_lines(self)
            if not self.material_request_id.livestock_cutting_material_line_ids:
                raise ValidationError("The selected product BOM has no component products.")
        self.end_time = fields.Datetime.now()
        self.state = 'done'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.cutting.material',
            'res_id': self.material_request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    
    def action_open_wizard(self):
        """Open a transient wizard to choose destination location"""
        
        self.ensure_one()
        self._check_order_transfer()

        return {
            'name': _('Order Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.slaugther.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_livestock_slaughter_id': self.id},
        }

    def action_open_bulk_transfer(self):
        """Open the transfer wizard for all selected records at once"""
        self._check_order_transfer()

        return {
            'name': _('Order Transfer'),
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