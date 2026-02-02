from odoo import models, fields, _
from odoo.exceptions import ValidationError, UserError


class LivestockSlaugtherWizard(models.TransientModel):
    _name = 'livestock.slaugther.wizard'
    _description = "Livestock Slaugther Wizard"


    dest_location_id = fields.Many2one('stock.location', string='Destination Location')
    livestock_slaughter_id = fields.Many2one('livestock.slaugther', string='Livestock Slaugther')


    def action_do_transfer(self):
        """Create an internal picking from 'Livestock Slaugther' to chosen destination,
        move the product and quantity from the slaughter record and validate it."""
        self.ensure_one()
        rec = self.livestock_slaughter_id

        # basic validations
        if not rec.product:
            raise ValidationError(_('Record has no product set.'))
        if not rec.quantity or rec.quantity <= 0:
            raise ValidationError(_('Quantity must be greater than 0.'))

        # find source location named "Livestock Slaugther"
        src_loc = self.env['stock.location'].search([('name', 'ilike', 'Livestock Slaugther')], limit=1)
        if not src_loc:
            raise UserError(_('Source location "Livestock Slaugther" not found. Please create it or rename appropriately.'))

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
        self.env['stock.move'].create(move_vals)

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