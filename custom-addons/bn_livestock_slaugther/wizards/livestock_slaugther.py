from collections import defaultdict

from odoo import models, fields, _
from odoo.exceptions import ValidationError, UserError


class LivestockSlaugtherWizard(models.TransientModel):
    _name = 'livestock.slaugther.wizard'
    _description = "Livestock Slaugther Wizard"


    dest_location_id = fields.Many2one('stock.location', string='Destination Location')
    livestock_slaughter_id = fields.Many2one('livestock.slaugther', string='Livestock Slaugther')
    livestock_slaughter_ids = fields.Many2many('livestock.slaugther', string='Selected Livestock')
    is_bulk = fields.Boolean('Bulk Transfer')
    remarks = fields.Text('Remarks')
    truck_number = fields.Char('Truck Number')
    total_quantity = fields.Integer('Total Quantity', compute='_compute_total_quantity')

    def _compute_total_quantity(self):
        for wizard in self:
            wizard.total_quantity = sum(wizard._get_records().mapped('quantity'))

    def _get_records(self):
        return self.livestock_slaughter_ids or self.livestock_slaughter_id

    def action_do_transfer(self):
        """Move the selected slaughtered animals from where Slaughtered put them
        (their department location, in their own warehouse) to the chosen
        destination: one validated picking per source location."""
        self.ensure_one()
        records = self._get_records()

        # basic validations
        if not records:
            raise ValidationError(_('No records selected for transfer.'))
        if not self.dest_location_id:
            raise ValidationError(_('Please select the destination location.'))
        if not (self.truck_number or '').strip():
            raise ValidationError(_('Please enter the truck number.'))
        records._check_order_transfer()
        for rec in records:
            if not rec.product_id:
                raise ValidationError(_('Record %s has no product set.') % rec.name)
            if not rec.quantity or rec.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than 0 (%s).') % rec.name)

        records_by_location = defaultdict(lambda: self.env['livestock.slaugther'])
        for rec in records:
            src_loc = rec._slaughtered_location()
            if src_loc == self.dest_location_id:
                raise ValidationError(_('%s is already at %s. Please select another destination.')
                                      % (rec.name, src_loc.display_name))
            records_by_location[src_loc] |= rec

        pickings = self.env['stock.picking']
        for src_loc, location_records in records_by_location.items():
            pickings |= self._create_transfer(src_loc, location_records)

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
            'res_id': pickings.id,
            'target': 'current',
        }

    def _create_transfer(self, src_loc, records):
        """One validated picking moving ``records`` out of ``src_loc``."""
        # choose internal picking type for the company (fallback to any internal if company-specific not found)
        picking_type = self.env['stock.warehouse']._get_program_type('livestock', src_loc)
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
            'note': self.remarks,
            'company_id': self.env.company.id,
        }
        if len(records) == 1:
            picking_vals['source_record_ref'] = '%s,%s' % (records._name, records.id)
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
            'transfer_remarks': self.remarks,
            'truck_number': self.truck_number.strip(),
        })
        return picking
