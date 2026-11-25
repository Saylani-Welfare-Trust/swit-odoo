from odoo import _, models, fields, api
from odoo.exceptions import ValidationError


state_selection = [
    ('not_received', 'Not Received'),
    ('received', 'Received'),
    ('in_progress', 'In Progress'),
    ('done', 'Done')
]


class LivestockCuttingMaterial(models.Model):
    _name = 'livestock.cutting.material'
    _description = "Livestock Cutting Material"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    product_id = fields.Many2one('product.product', string="Product")
    livestock_slaughter_id = fields.Many2one('livestock.slaugther', string='Livestock Slaughter', copy=False)
    # where the animal is cut, and where its meat / other products go: locations
    # marked Is Cutting / Is Meat / Is Goat Location (a warehouse may hold several)
    cutting_location_id = fields.Many2one(
        'stock.location', string='Cutting Location', copy=False, domain="[('is_cutting_location', '=', True)]")
    meat_location_id = fields.Many2one(
        'stock.location', string='Meat Location', copy=False, domain="[('is_meat_location', '=', True)]",
        help="Where Send to Goat and Meat puts the meat products.")
    goat_location_id = fields.Many2one(
        'stock.location', string='Goat Location', copy=False, domain="[('is_goat_location', '=', True)]",
        help="Where Send to Goat and Meat puts the other cut products.")
    # the warehouse the animal is cut in: of its cutting location
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', copy=False,
                                   compute='_compute_warehouse_id', store=True, readonly=True)

    @api.depends('cutting_location_id')
    def _compute_warehouse_id(self):
        for record in self:
            record.warehouse_id = record.cutting_location_id.warehouse_id or record.warehouse_id

    @api.onchange('cutting_location_id')
    def _onchange_cutting_location_id(self):
        warehouse = self.cutting_location_id.warehouse_id
        Location = self.env['stock.location']
        for field, role in (('meat_location_id', 'is_meat_location'), ('goat_location_id', 'is_goat_location')):
            if warehouse and (not self[field] or self[field].warehouse_id != warehouse):
                self[field] = Location._single_role_location(role, warehouse)

    def _fill_default_locations(self):
        """Empty locations get the only one of their role: the cutting location of
        the slaughter record or of its warehouse, and the Meat / Goat locations
        of the cutting location's warehouse."""
        Location = self.env['stock.location']
        for record in self.sudo():
            if not record.cutting_location_id:
                record.cutting_location_id = record.livestock_slaughter_id.cutting_location_id or \
                    Location._single_role_location('is_cutting_location', record._livestock_warehouse())
            warehouse = record.cutting_location_id.warehouse_id
            if not record.meat_location_id:
                record.meat_location_id = Location._single_role_location('is_meat_location', warehouse)
            if not record.goat_location_id:
                record.goat_location_id = Location._single_role_location('is_goat_location', warehouse)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._fill_default_locations()
        return records

    def _required_location(self, field):
        self.ensure_one()
        if not self[field]:
            self._fill_default_locations()
        if not self[field]:
            raise ValidationError(_("Choose the %(field)s of %(record)s.",
                                    field=self._fields[field].string, record=self.name or self.code))
        return self[field]
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)

    name = fields.Char(related='product_id.name', string="Product Name")
    code = fields.Char(related='product_id.default_code', string="Product Code", store=True)

    quantity = fields.Integer('Quantity', default=1)

    price = fields.Monetary('Price', currency_field='currency_id', default=0)

    state = fields.Selection(selection=state_selection, string="State", default='not_received')
    # each stock step is done once (Update Inventory, then Send to Goat & Meat)
    inventory_updated = fields.Boolean('Inventory Updated', readonly=True, copy=False)
    materials_sent = fields.Boolean('Materials Sent', readonly=True, copy=False)

    start_time = fields.Datetime('Start Time')

    end_time = fields.Datetime('End Time')

    total_time = fields.Char('Total Time (H:M:S)', compute='_compute_total_time', store=True)

    livestock_cutting_material_line_ids = fields.One2many('livestock.cutting.material.line', 'livestock_cutting_material_id', string='Livestock Cutting Material Lines')

    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for line in self:
            line.on_hand_qty = line.product_id.qty_available if line.product_id else 0.0

    def _get_product_bom(self):
        self.ensure_one()
        if not self.product_id:
            return self.env['mrp.bom']
        bom_model = self.env['mrp.bom']
        bom = bom_model.search([
            ('product_id', '=', self.product_id.id),
        ], order='sequence, id', limit=1)
        if not bom:
            bom = bom_model.search([
                ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id),
                ('product_id', '=', False),
            ], order='sequence, id', limit=1)
        return bom

    def _populate_bom_lines(self, livestock_slaughter=False):
        for material in self:
            bom = material._get_product_bom()
            lines = [(5, 0, 0)]
            if bom:
                for bom_line in bom.bom_line_ids.filtered('product_id'):
                    lines.append((0, 0, {
                        'livestock_slaughter_id': livestock_slaughter.id if livestock_slaughter else False,
                        'product_id': bom_line.product_id.id,
                        'quantity': (bom_line.product_qty / bom.product_qty) * material.quantity
                        if bom.product_qty else bom_line.product_qty,
                    }))
            if material.id:
                material.write({'livestock_cutting_material_line_ids': lines})
            else:
                material.livestock_cutting_material_line_ids = lines

    @api.depends('start_time', 'end_time')
    def _compute_total_time(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                duration = rec.end_time - rec.start_time
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60

                rec.total_time = f"{hours:02}:{minutes:02}:{seconds:02}"
            else:
                rec.total_time = "00:00:00"


    def action_confirm(self):
        for record in self:
            if record.state == 'not_received':
                record.state = 'received'
                if record.livestock_slaughter_id and record.livestock_slaughter_id.state == 'cutting':
                    record.livestock_slaughter_id.state = 'material_request'

    def _stock_move(self, product, qty, source, destination):
        """Move ``qty`` of ``product`` with a validated stock move (traceable and
        valued), refusing when the source location does not have it."""
        self.ensure_one()
        if qty <= 0:
            return self.env['stock.move']
        # the button is the Livestock group's: the stock step itself is done as superuser
        if source.usage == 'internal':
            available = product.sudo().with_context(location=source.id).qty_available
            if available < qty:
                raise ValidationError(
                    "Not enough %s in %s (%s available, need %s)."
                    % (product.display_name, source.display_name, available, qty))
        move = self.env['stock.move'].sudo().create({
            'name': '%s: %s' % (self.code or self.name or 'Livestock', product.display_name),
            'origin': self.name or self.code,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': qty,
            'location_id': source.id,
            'location_dest_id': destination.id,
            'company_id': self.env.company.id,
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = qty
        move.picked = True
        move._action_done()
        return move

    def _livestock_warehouse(self):
        """The warehouse the animal is cut in: of its cutting location, else its
        slaughter record's, else its Branch / Site's."""
        self.ensure_one()
        if self.cutting_location_id.warehouse_id:
            return self.cutting_location_id.warehouse_id
        if self.livestock_slaughter_id:
            return self.livestock_slaughter_id._livestock_warehouse()
        try:
            return self.env['stock.warehouse']._warehouse_for(branch=self.node_id)
        except Exception:
            return self.env['stock.warehouse']

    def _cutting_location(self):
        return self._required_location('cutting_location_id')

    def action_update_inventory(self):
        """The materials of the cutting enter the Cutting location (once)."""
        for record in self:
            cutting_loc = record._cutting_location()
            if record.state != 'not_received':
                raise ValidationError("Inventory can only be updated before the material is received.")
            if record.inventory_updated:
                raise ValidationError("The inventory of %s is already updated." % (record.name or record.code))
            # the cut animal is used up: it leaves the Cutting location (its material
            # request was made with the cutting, which put it there)
            slaughter = record.livestock_slaughter_id
            if slaughter and slaughter.cutting_material_id == record and record.product_id:
                animal = record.product_id
                record._stock_move(animal, record.quantity, cutting_loc,
                                   animal.with_company(self.env.company).property_stock_inventory)
            for material in record.livestock_cutting_material_line_ids:
                product = material.product_id
                record._stock_move(product, material.quantity,
                                   product.with_company(self.env.company).property_stock_inventory, cutting_loc)
            record.inventory_updated = True

    def action_send_to_goat_and_meat(self):
        """The materials go from the Cutting location to Meat (meat products) or Goat (once)."""
        for record in self:
            cutting_loc = record._required_location('cutting_location_id')
            goat_loc = record._required_location('goat_location_id')
            meat_loc = record._required_location('meat_location_id')
            if record.state != 'not_received':
                raise ValidationError("Materials can only be sent before the material is received.")
            if not record.inventory_updated:
                raise ValidationError("Update the inventory of %s first." % (record.name or record.code))
            if record.materials_sent:
                raise ValidationError("The materials of %s are already sent." % (record.name or record.code))
            for material in record.livestock_cutting_material_line_ids:
                product = material.product_id
                target_loc = meat_loc if 'meat' in (product.name or '').lower() else goat_loc
                record._stock_move(product, material.quantity, cutting_loc, target_loc)
            # the last step: the request and its animal are done
            record.write({'materials_sent': True, 'state': 'done'})
            if record.livestock_slaughter_id.state in ('cutting', 'material_request'):
                record.livestock_slaughter_id.state = 'done'
