from odoo import models, fields, api
from odoo.exceptions import ValidationError


state_selection = [
    ('not_received', 'Not Received'),
    ('received', 'Received'),
    ('in_progress', 'In Progress'),
    ('done', 'Done')
]


class LivestockCuttingMaterial(models.Model):
    _name = 'livestock.cutting.material'
    _descripiton = "Livestock Cutting Material"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)

    name = fields.Char(related='product_id.name', string="Product Name", store=True)
    code = fields.Char(related='product_id.default_code', string="Product Code", store=True)

    quantity = fields.Integer('Quantity', default=1)

    price = fields.Monetary('Price', currency_field='currency_id', default=0)

    state = fields.Selection(selection=state_selection, string="State", default='not_received')

    start_time = fields.Datetime('Start Time')

    end_time = fields.Datetime('End Time')

    total_time = fields.Char('Total Time (H:M:S)', compute='_compute_total_time', store=True)

    livestock_cutting_material_line_ids = fields.One2many('livestock.cutting.material.line', 'livestock_cutting_material_id', string='Livestock Cutting Material Lines')


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
        self.state = 'received'

    def action_update_inventory(self):
        # 1) find the Cutting location record
        cutting_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'Livestock Cutting')
        ], limit=1)
        if not cutting_loc:
            raise ValidationError("No such location as (Livestock Cutting) found!")

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

    def action_send_to_goat_and_meat(self):
        # 1) Find Cutting, Goat, and Meat locations
        cutting_loc = self.env['stock.location'].search([('name', 'ilike', 'Livestock Cutting')], limit=1)
        goat_loc = self.env['stock.location'].search([('name', 'ilike', 'Livestock Goat')], limit=1)
        meat_loc = self.env['stock.location'].search([('name', 'ilike', 'Livestock Meat')], limit=1)

        if not cutting_loc or not goat_loc or not meat_loc:
            raise ValidationError("Cutting, Goat, or Meat location not properly set!")

        for material in self.material_ids:
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
                raise ValidationError(f"No stock.quant forM')], l {product.name} in Cutting location.")
            if cutting_quant.quantity < qty:
                raise ValidationError(
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

    def action_start(self):
        product_master = self.env['product.master']
        needed_parents = product_master.search([('product_id', '=', self.product.id)], limit=1)

        self.state = 'in_progress'
        self.start_time = fields.Datetime.now()

        material_vals = []

        # Add main parent product(s)
        for parent in needed_parents:
            for line in parent.line_ids:
                material_vals.append((0, 0, {
                    'product': line.product_id.id,
                    'quantity': line.quantity,
                }))

        self.material_ids = material_vals

    def action_end(self):
        self.state = 'done'
        self.end_time = fields.Datetime.now()

        # 1) find the Cutting location
        cutting_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'Livestock Cutting')
        ], limit=1)
        if not cutting_loc:
            raise ValidationError("No such location Livestock Cutting found!")

        # 2) for each material line, subtract from that location’s quant
        product = self.product
        used_qty = self.quantity

        # find the quant in Cutting location
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', cutting_loc.id),
        ], limit=1)

        if not quant:
            raise ValidationError(f"No stock.quant for {self.product.name} in Livestock Cutting location to deduct from.")
        if quant.quantity < used_qty:
            raise ValidationError(
                f"Not enough {self.product.name} in Livestock Cutting location "
                f"({quant.quantity} available, need {used_qty})."
            )

        # subtract the used quantity
        quant.quantity -= used_qty