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
    livestock_slaughter_id = fields.Many2one('livestock.slaugther', string='Livestock Slaughter', copy=False)
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

    def action_update_inventory(self):
        # 1) find the Cutting location record
        cutting_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'Livestock Cutting')
        ], limit=1)
        if not cutting_loc:
            raise ValidationError("No such location as (Livestock Cutting) found!")

        # 2) for each material, bump the quant in that cutting location
        for record in self:
            for material in record.livestock_cutting_material_line_ids:
                product = material.product_id
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
        cutting_loc = self.env['stock.location'].search([('name', 'ilike', 'Cutting')], limit=1)
        goat_loc = self.env['stock.location'].search([('name', 'ilike', 'Goat')], limit=1)
        meat_loc = self.env['stock.location'].search([('name', 'ilike', 'Meat')], limit=1)

        if not cutting_loc or not goat_loc or not meat_loc:
            raise ValidationError("Cutting, Goat, or Meat location not properly set!")

        for material in self.livestock_cutting_material_line_ids:
            product = material.product_id
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

    def action_start_cutting(self):
        for record in self:
            if record.state != 'received':
                raise ValidationError("Cutting can only be started after the material request is confirmed.")
            record.state = 'in_progress'
            record.start_time = record.start_time or fields.Datetime.now()
            if record.livestock_slaughter_id:
                record.livestock_slaughter_id.state = 'material_request'
                record.livestock_slaughter_id.start_time = record.start_time

    def action_end_cutting(self):
        self.ensure_one()
        if self.state != 'in_progress':
            raise ValidationError("End Cutting is available only after cutting has started.")
        if not self.product_id:
            raise ValidationError("Please select a product before ending cutting.")
        if not self.livestock_cutting_material_line_ids:
            self._populate_bom_lines()
        if not self.livestock_cutting_material_line_ids:
            raise ValidationError(
                "No BOM component products found for %s." % self.product_id.display_name
            )

        # 1) find the Cutting location
        cutting_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'Livestock Cutting')
        ], limit=1)
        if not cutting_loc:
            raise ValidationError("No such location Livestock Cutting found!")

        # 2) for each material line, subtract from that location’s quant
        product = self.product_id
        used_qty = self.quantity

        # find the quant in Cutting location
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', cutting_loc.id),
        ], limit=1)

        if not quant:
            raise ValidationError(f"No stock.quant for {product.display_name} in Livestock Cutting location to deduct from.")
        if quant.quantity < used_qty:
            raise ValidationError(
                f"Not enough {product.display_name} in Livestock Cutting location "
                f"({quant.quantity} available, need {used_qty})."
            )

        # subtract the used quantity
        quant.quantity -= used_qty
        self.state = 'done'
        self.end_time = fields.Datetime.now()
        if self.livestock_slaughter_id:
            self.livestock_slaughter_id.end_time = self.end_time
            self.livestock_slaughter_id.state = 'done'