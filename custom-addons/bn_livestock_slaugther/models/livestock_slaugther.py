from odoo import models, fields, _, api
from odoo.exceptions import ValidationError


state_selection = [
    ('not_received', 'Draft'),
    ('received', 'Received'),
    ('cutting', 'Cutting'),
    ('material_request', 'Material Request'),
    ('done', 'Done')
]


class LivestockSlaughter(models.Model):
    _name = 'livestock.slaugther'
    _description = "Livestock Slaugther"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    donee_id = fields.Many2one('res.partner', string="Donee")
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
    material_request_line_ids = fields.One2many(
        related='material_request_id.livestock_cutting_material_line_ids',
        string='Material Request Lines',
        readonly=True,
    )
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
    transfer_location = fields.Many2one('stock.location', string='Destination Location')
    source_location_id = fields.Many2one('stock.location', string='Source Location')
    transfer_picking_id = fields.Many2one('stock.picking', string='Transfer', copy=False, readonly=True)
    transfer_remarks = fields.Text('Transfer Remarks', copy=False)

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
    confirm_hide = fields.Boolean('Confirm Hide')
    cutting_hide = fields.Boolean('Cutting Hide')
    transfer_bool = fields.Boolean('Cutting Hide')

    _sql_constraints = [
        (
            'unique_pos_order_line_id',
            'unique(pos_order_line_id)',
            'A livestock slaughter record already exists for this POS order line.',
        ),
        (
            'unique_direct_deposit_line_id',
            'unique(direct_deposit_line_id)',
            'A livestock slaughter record already exists for this Direct Deposit line.',
        ),
        (
            'unique_donation_id',
            'unique(donation_id)',
            'A livestock slaughter record already exists for this Donation.',
        ),
        (
            'unique_api_donation_item_id',
            'unique(api_donation_item_id)',
            'A livestock slaughter record already exists for this API Donation item.',
        ),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            if vals.get('is_meat_depart'):
                vals['name'] = self.env['ir.sequence'].next_by_code('meat_department') or ('New')
            elif vals.get('is_goat_depart'):
                vals['name'] = self.env['ir.sequence'].next_by_code('goat_department') or ('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('livestock_slaugther') or ('New')

        return super(LivestockSlaughter, self).create(vals)

    def action_confirm(self):
        self.ensure_one()
        if self.state != 'not_received':
            return
        # Retrieve the 'Slaughter Stock' location
        location = None

        if self.is_meat_depart:
            location = self.env['stock.location'].search([('name', '=', 'Meat')], limit=1)
        elif self.is_goat_depart:
            location = self.env['stock.location'].search([('name', '=', 'Goat')], limit=1)
        else:
            location = self.env['stock.location'].search([('name', '=', 'Slaughter Stock')], limit=1)
        
        if not location:
            raise ValidationError("Slaughter Stock, Meat or Goat location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise ValidationError("Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        # Retrieve the product based on the product code
        product = self.product_id
        if not product:
            raise ValidationError(f"Product with code '{self.code}' not found.")

        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': location.id,
            'origin': self.product_id or 'Live Stock Slaughter',
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
        self.state = 'received'

    def action_cutting(self):
        self.ensure_one()
        if self.state != 'received':
            raise ValidationError("Cutting can only be started after confirmation.")
        if not self.product_id:
            raise ValidationError("Please select a product before starting cutting.")

        location = self.env['stock.location'].search([('name', '=', 'Livestock Cutting')], limit=1)
        if not location:
            raise ValidationError("Livestock Cutting location not found. Please create it in Inventory > Configuration > Locations.")

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise ValidationError("Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        product = self.product_id

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': location.id,
            'origin': self.product_id.id or '',
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
        
        return self.env['livestock.slaugther.wizard']._open_for(self, _('Transfer from Slaughter Stock'))

    def action_open_bulk_transfer(self):
        """Open the transfer wizard for all selected records at once"""
        if not self:
            raise ValidationError(_("Please select the records to transfer."))
        transferred = self.filtered('transfer_bool')
        if transferred:
            raise ValidationError(
                _("These records are already transferred:\n%s")
                % "\n".join(transferred.mapped(lambda r: '%s - %s' % (r.name, r.product_id.display_name)))
            )

        return self.env['livestock.slaugther.wizard']._open_for(self, _('Bulk Transfer'), is_bulk=True)

    def _get_expected_location(self):
        """Location this record's animal was moved to by its last step"""
        self.ensure_one()
        Location = self.env['stock.location']
        if self.state == 'received':
            if self.is_meat_depart:
                name = 'Meat'
            elif self.is_goat_depart:
                name = 'Goat'
            else:
                name = 'Slaughter Stock'
        elif self.state in ('cutting', 'material_request', 'done'):
            name = 'Livestock Cutting'
        else:
            # not confirmed yet: still where action_confirm takes it from
            return self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id.company_id', '=', self.env.company.id)
            ], limit=1).default_location_src_id
        return Location.search([('name', '=', name)], limit=1)

    def _suggest_source_locations(self):
        """Return {record id: location id} with where each product currently
        has stock. The location of the record's last step is preferred, then
        the location holding the most stock. Quantities already given to
        earlier records are deducted so two records don't take the same unit.
        Without any stock, the location of the record's last step is used,
        and finally the 'Livestock Slaugther' location."""
        default_location = self.env['stock.location'].search([('name', 'ilike', 'Livestock Slaugther')], limit=1)
        stock = {
            (product.id, location.id): quantity
            for product, location, quantity in self.env['stock.quant']._read_group(
                [
                    ('product_id', 'in', self.product_id.ids),
                    ('location_id.usage', 'in', ['internal', 'transit']),
                    ('location_id.company_id', 'in', [self.env.company.id, False]),
                    ('quantity', '>', 0),
                ],
                ['product_id', 'location_id'],
                ['quantity:sum'],
            )
        }
        result = {}
        for rec in self:
            available = {
                location_id: quantity
                for (product_id, location_id), quantity in stock.items()
                if product_id == rec.product_id.id and quantity > 0
            }
            expected = rec._get_expected_location()
            if expected and available.get(expected.id, 0) >= rec.quantity:
                location_id = expected.id
            elif available:
                location_id = max(available, key=available.get)
            else:
                location_id = expected.id or default_location.id
            if (rec.product_id.id, location_id) in stock:
                stock[(rec.product_id.id, location_id)] -= rec.quantity
            result[rec.id] = location_id
        return result

    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for line in self:
            line.on_hand_qty = line.product_id.qty_available if line.product_id else 0.0