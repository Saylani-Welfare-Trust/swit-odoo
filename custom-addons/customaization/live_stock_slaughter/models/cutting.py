from odoo import models, fields, api
from odoo.exceptions import UserError


class live_stock_slaughter_cutting_material(models.Model):
    _name = 'live_stock_slaughter.cutting_material'
    _description = 'live_stock_slaughter.cutting_material'
    _rec_company_auto = True

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    product = fields.Many2one('product.product', string="Product", required=True)

    quantity = fields.Integer(
        string='Quantity',
    )

    price = fields.Float(
        string='Price',
    )

    product_code = fields.Char(
        string='Product Code',
        required=False)

    confirm_hide = fields.Boolean(
        string='Confirm_hide',
        required=False)

    cutting_hide = fields.Boolean(
        string='Confirm_hide',
        required=False)

    picking_id = fields.Many2one('stock.picking', string="Picking")

    state = fields.Selection([
        ('not_received', 'Not Received'),
        ('received', 'Received'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], default='not_received', string="Status")

    start_time = fields.Datetime(
        string='Start Time',
        required=False)

    end_time = fields.Datetime(
        string='End Time',
        required=False)

    total_time = fields.Char(  # <-- Change to Char field now
        string='Total Time (H:M:S)',
        compute='_compute_total_time',
        store=True,
        readonly=True,
    )

    material_ids = fields.One2many(
        comodel_name='cutting.material_ids',
        inverse_name='material_id',
        string='Material_ids',
        required=False)

    hide_update = fields.Boolean(
        string='Hide_update',
        required=False)

    hide_goat = fields.Boolean(
        string='hide_goat',
        required=False)

    @api.depends('start_time', 'end_time')
    def _compute_total_time(self):
        for record in self:
            if record.start_time and record.end_time:
                duration = record.end_time - record.start_time
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                record.total_time = f"{hours:02}:{minutes:02}:{seconds:02}"
            else:
                record.total_time = "00:00:00"

    def action_confirm(self):
        for record in self:
            record.state = 'received'

    def action_start(self):
        ProductParent = self.env['product.parent']
        needed_parents = ProductParent.search([('product_id', '=', self.product.id)], limit=1)

        for record in self:
            record.state = 'in_progress'
            record.start_time = fields.Datetime.now()

            material_vals = []

            # Add main parent product(s)
            for parent in needed_parents:
                for line in parent.line_ids:
                    material_vals.append((0, 0, {
                        'product': line.product_id.id,
                        'quantity': line.quantity,
                    }))

            record.material_ids = material_vals

    def action_start3222(self):
        Product = self.env['product.parent']
        needed_products = Product.search([('product_id', '=', self.product.id)])

        for record in self:
            record.state = 'in_progress'
            record.start_time = fields.Datetime.now()

            material_vals = []
            for product in needed_products:
                material_vals.append((0, 0, {
                    'product': product.id,
                    'quantity': 1.0,
                }))

            record.material_ids = material_vals

    def action_end(self):
        for record in self:
            record.state = 'done'
            record.end_time = fields.Datetime.now()

            # 1) find the Cutting location
            cutting_loc = self.env['stock.location'].search([
                ('name', 'ilike', 'cutting')
            ], limit=1)
            if not cutting_loc:
                raise UserError("No stock.location with name containing 'cutting' found!")

                # 2) for each material line, subtract from that location’s quant
            product = self.product
            used_qty = record.quantity

            # find the quant in Cutting location
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', '=', cutting_loc.id),
            ], limit=1)

            if not quant:
                raise UserError(
                    f"No stock.quant for {record.product.name} in Cutting location to deduct from."
                )
            if quant.quantity < used_qty:
                raise UserError(
                    f"Not enough {record.product.name} in Cutting location "
                    f"({quant.quantity} available, need {used_qty})."
                )

            # subtract the used quantity
            quant.quantity -= used_qty

    def action_up_inventory(self):
        # 1) find the Cutting location record
        cutting_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'cutting')
        ], limit=1)
        if not cutting_loc:
            raise UserError("No stock.location with usage='cutting' found!")

        # 2) for each material, bump the quant in that cutting location
        for record in self:
            for material in record.material_ids:
                product = material.product
                qty = material.quantity

                # find or create the quant in the Cutting location
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', cutting_loc.id),
                ], limit=1)
                if quant:
                    quant.quantity += qty
                else:
                    self.env['stock.quant'].create({
                        'product_id': product.id,
                        'location_id': cutting_loc.id,
                        'quantity': qty,
                    })
            record.hide_update = True

    def action_to_goat_and_meat_dept(self):
        for record in self:
            # 1) Find Cutting, Goat, and Meat locations
            cutting_loc = self.env['stock.location'].search([('name', 'ilike', 'cutting')], limit=1)
            goat_loc = self.env['stock.location'].search([('name', 'ilike', 'goat')], limit=1)
            meat_loc = self.env['stock.location'].search([('name', 'ilike', 'meat')], limit=1)

            if not cutting_loc or not goat_loc or not meat_loc:
                raise UserError("Cutting, Goat, or Meat location not properly set!")

            for material in record.material_ids:
                product = material.product
                qty = material.quantity

                # Decide target location
                if 'meat' in product.name.lower():
                    target_loc = meat_loc
                else:
                    target_loc = goat_loc

                # 2) Deduct from Cutting location
                cutting_quant = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', cutting_loc.id),
                ], limit=1)

                if not cutting_quant:
                    raise UserError(f"No stock.quant for {product.name} in Cutting location.")
                if cutting_quant.quantity < qty:
                    raise UserError(
                        f"Not enough {product.name} in Cutting location (Available {cutting_quant.quantity}, need {qty}).")

                cutting_quant.quantity -= qty

                # 3) Add to target location
                target_quant = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', target_loc.id),
                ], limit=1)

                if target_quant:
                    target_quant.quantity += qty
                else:
                    self.env['stock.quant'].create({
                        'product_id': product.id,
                        'location_id': target_loc.id,
                        'quantity': qty,
                    })

            record.hide_goat = True


class cutting_material_ids(models.Model):
    _name = 'cutting.material_ids'
    _description = 'cutting.material_ids'

    material_id = fields.Many2one(
        comodel_name='live_stock_slaughter.cutting_material',
        string='material_id',
        required=False)

    product = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=False)

    quantity = fields.Float(
        string='Quantity',
        required=False)
