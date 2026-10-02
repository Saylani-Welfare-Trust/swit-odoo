from odoo import models, fields, _
from odoo.exceptions import ValidationError, UserError


class LivestockSlaugtherWizard(models.TransientModel):
    _name = 'livestock.slaugther.wizard'
    _description = "Livestock Slaugther Wizard"


    def _default_source_location(self):
        return self.env['stock.location'].search([('name', 'ilike', 'Livestock Slaugther')], limit=1)

    source_location_id = fields.Many2one('stock.location', string='Source Location', default=_default_source_location, readonly=True)
    dest_location_id = fields.Many2one('stock.location', string='Destination Location')
    livestock_slaughter_id = fields.Many2one('livestock.slaugther', string='Livestock Slaugther')
    livestock_slaughter_ids = fields.Many2many('livestock.slaugther', string='Selected Livestock')
    is_bulk = fields.Boolean('Bulk Transfer')
    total_quantity = fields.Integer('Total Quantity', compute='_compute_total_quantity')

    def _compute_total_quantity(self):
        for wizard in self:
            wizard.total_quantity = sum(wizard._get_records().mapped('quantity'))

    def _get_records(self):
        return self.livestock_slaughter_ids or self.livestock_slaughter_id

    def action_do_transfer(self):
        """Create an internal picking from 'Livestock Slaugther' to chosen destination,
        move the product and quantity of every selected slaughter record and validate it."""
        self.ensure_one()
        records = self._get_records()

        # basic validations
        if not records:
            raise ValidationError(_('No records selected for transfer.'))
        if not self.dest_location_id:
            raise ValidationError(_('Please select the destination location.'))
        transferred = records.filtered('transfer_bool')
        if transferred:
            raise ValidationError(_('Already transferred: %s') % ', '.join(transferred.mapped('name')))
        for rec in records:
            if not rec.product_id:
                raise ValidationError(_('Record %s has no product set.') % rec.name)
            if not rec.quantity or rec.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than 0 (%s).') % rec.name)

        # source location named "Livestock Slaugther"
        src_loc = self.source_location_id or self._default_source_location()
        if not src_loc:
            raise UserError(_('Source location "Livestock Slaugther" not found. Please create it or rename appropriately.'))

        # choose internal picking type for the company (fallback to any internal if company-specific not found)
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
        if not picking_type:
            raise UserError(_('No internal picking type found. Configure a Warehouse with an Internal Transfers type.'))

        # Build picking
        donees = records.mapped('donee_id')
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': src_loc.id,
            'location_dest_id': self.dest_location_id.id,
            'partner_id': donees.id if len(donees) == 1 else False,
            'origin': ', '.join(records.mapped('name')) or _('Slaughter Transfer'),
            'company_id': self.env.company.id,
        }
        picking = self.env['stock.picking'].create(picking_vals)

        # Build one move per record
        for rec in records:
            # ensure we have a concrete product.product
            product = getattr(rec.product_id, 'product_variant_id', False) or (
                        rec.product_id.product_variant_ids and rec.product_id.product_variant_ids[0])
            if not product:
                raise UserError(_('No product variant found for template: %s') % rec.product_id.display_name)

            self.env['stock.move'].create({
                'name': product.display_name,
                'product_id': product.id,
                'product_uom_qty': rec.quantity,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': src_loc.id,
                'location_dest_id': self.dest_location_id.id,
                'company_id': self.env.company.id,
            })

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

        records.write({
            'source_location_id': src_loc.id,
            'transfer_location': self.dest_location_id.id,
            'transfer_picking_id': picking.id,
            'transfer_bool': True,
        })

        if self.is_bulk:
            # Print the bulk transfer slip and close the wizard
            action = self.env.ref('bn_livestock_slaugther.action_report_livestock_bulk_transfer').report_action(records)
            action['close_on_report_download'] = True
            return action

        # Return action to open the picking (optional)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }
