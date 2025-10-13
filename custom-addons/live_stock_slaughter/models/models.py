from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import UserError, ValidationError


class live_stock_slaughter(models.Model):
    _name = 'live_stock_slaughter.live_stock_slaughter'
    _description = 'live_stock_slaughter.live_stock_slaughter'
    _rec_company_auto = True

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    ext_url = fields.Char("Backend URL")  # stores internal URL
    qr_code = fields.Binary("QR Code (PNG)")  # binary QR image (base64)
    qr_mime = fields.Char("QR MIME", default='image/png')

    transfer_bool = fields.Boolean(
        string='Transfer_bool',
        required=False)

    access_token = fields.Char("Access Token")  # optional, see public URL section

    product = fields.Many2one('product.template', string="Product", required=False)

    product_new = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=False)

    transfer_location = fields.Many2one(
        'stock.location', string='Transfer Location', required=True,
    )

    pos_name = fields.Char(
        string='POS Order Ref',
        required=False)

    quantity = fields.Integer(
        string='Quantity',
    )

    price = fields.Float(
        string='Price',
    )

    donee = fields.Many2one(
        comodel_name='res.partner',
        string='Donee',
        required=False)

    product_code = fields.Char(
        string='Product Code',
        required=False)

    confirm_hide = fields.Boolean(
        string='Confirm_hide',
        required=False)

    cutting_hide = fields.Boolean(
        string='Confirm_hide',
        required=False)

    state = fields.Selection(
        string='State',
        selection=[('not_received', 'Not Received'),
                   ('received', 'Received'), ],
        default='not_received',
        required=False, )
    origin = fields.Char(string='Source Document',)

    def action_confirm(self):
        # Retrieve the 'Slaughter Stock' location

        slaughter_location = self.env['stock.location'].search([('name', '=', 'Slaughter Stock')], limit=1)
        if not slaughter_location:
            raise UserError(
                "Slaughter Stock location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise UserError(
                "Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        # Retrieve the product based on the product code
        product = self.product_new
        if not product:
            raise UserError(f"Product with code '{self.product_code}' not found.")

        if self.transfer_location:
            destination_location = self.transfer_location.id
        else:
            destination_location = slaughter_location.id

        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': destination_location,
            'origin': self.product or 'Live Stock Slaughter',
        })

        # Create the stock move
        move = self.env['stock.move'].create({
            'name': product.display_name,
            'product_id': product.id,
            'product_uom_qty': self.quantity,
            'quantity': self.quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })

        print('moveeee', move)

        # Confirm and assign the picking
        picking.action_confirm()
        picking.action_assign()

        # Set the done quantities and validate the picking
        for move_line in picking.move_line_ids:
            move_line.quantity = move_line.quantity_product_uom
        picking.button_validate()

        self.confirm_hide = True
        self.state = 'received'

        return True

    def action_cutting(self):
        # Retrieve the 'Slaughter Stock' location
        cutting_obj = self.env['live_stock_slaughter.cutting']

        slaughter_location = self.env['stock.location'].search([('name', '=', 'Cutting')], limit=1)
        if not slaughter_location:
            raise UserError(
                "Cutting location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise UserError(
                "Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        # Retrieve the product based on the product code
        product = self.product_new


        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': slaughter_location.id,
            'origin': self.product_new.id or '',
        })

        # Create the stock move
        move = self.env['stock.move'].create({
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
        # for move_line in picking.move_line_ids:
        #     move_line.quantity = move_line.quantity_product_uom
        picking.button_validate()
        cutting_record = cutting_obj.create({
            'product_new': self.product_new.id,
            'quantity': self.quantity,
            'price': self.price,
            'product_code': self.product_code,
            'picking_id': picking.id,
        })

        self.cutting_hide = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Cutting Record',
            'res_model': 'live_stock_slaughter.cutting',
            'res_id': cutting_record.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_transfer_wizard(self):
        """Open a transient wizard to choose destination location"""
        self.ensure_one()
        return {
            'name': _('Transfer from Slaughter Stock'),
            'type': 'ir.actions.act_window',
            'res_model': 'live.stock.slaughter.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_slaughter_id': self.id},
        }


class LiveStockSlaughterTransferWizard(models.TransientModel):
    _name = 'live.stock.slaughter.transfer.wizard'
    _description = 'Transfer Slaughter Stock Wizard'

    slaughter_id = fields.Many2one(
        'live_stock_slaughter.live_stock_slaughter',
        string='Record',
        required=True,
        ondelete='cascade',
    )
    dest_location_id = fields.Many2one(
        'stock.location', string='Destination Location', required=True,
    )

    def action_do_transfer(self):
        """Create an internal picking from 'Slaughter Stock' to chosen destination,
        move the product and quantity from the slaughter record and validate it."""
        self.ensure_one()
        rec = self.slaughter_id

        # basic validations
        if not rec.product:
            raise ValidationError(_('Record has no product set.'))
        if not rec.quantity or rec.quantity <= 0:
            raise ValidationError(_('Quantity must be greater than 0.'))

        # find source location named "Slaughter Stock"
        src_loc = self.env['stock.location'].search([('name', 'ilike', 'Slaughter Stock')], limit=1)
        if not src_loc:
            raise UserError(_('Source location "Slaughter Stock" not found. Please create it or rename appropriately.'))

        # choose internal picking type for the company (fallback to any internal if company-specific not found)
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', rec.company_id.id)
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
        if not picking_type:
            raise UserError(_('No internal picking type found. Configure a Warehouse with an Internal Transfers type.'))

        # ensure we have a concrete product.product
        product = getattr(rec.product, 'product_variant_id', False) or (
                    rec.product.product_variant_ids and rec.product.product_variant_ids[0])
        if not product:
            raise UserError(_('No product variant found for template: %s') % rec.product.display_name)

        # Build picking
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': src_loc.id,
            'location_dest_id': self.dest_location_id.id,
            'partner_id': rec.donee.id if rec.donee else False,
            'origin': rec.pos_name or _('Slaughter Transfer'),
            'company_id': rec.company_id.id,
        }
        picking = self.env['stock.picking'].create(picking_vals)

        # Build move
        move_vals = {
            'name': product.display_name,
            'product_id': product.id,
            'product_uom_qty': rec.quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': src_loc.id,
            'location_dest_id': self.dest_location_id.id,
            'company_id': rec.company_id.id,
        }
        move = self.env['stock.move'].create(move_vals)

        # Confirm, assign, set done quantities and validate
        picking.action_confirm()
        try:
            picking.action_assign()
        except Exception:
            # Some configurations need force_assign
            picking._action_assign()  # fallback - in many Odoo versions this reserves or raises

        # Set done qtys on moves
        for mv in picking.move_ids:
            mv.quantity = mv.product_uom_qty

        # Validate (this will create stock.move.line if needed and finish the picking)
        picking.button_validate()

        # Optionally, you can change the state of the slaughter record
        # rec.state = 'received'  # or whatever makes sense
        rec.transfer_location = self.dest_location_id.id
        rec.transfer_bool = True

        # Return action to open the picking (optional)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }
