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
        """One validated picking per location of the animals:

        - Order Transfer (Draft lines): from the chosen location into the
          location where the animal waits for slaughter (its POS location, else
          its warehouse's), then the transfer is opened.
        - Bulk Transfer (Slaughtered lines, with a truck number): from where
          Slaughtered put the animal (its department location) to the chosen
          location, then the slip is printed."""
        self.ensure_one()
        records = self._get_records()

        # basic validations
        if not records:
            raise ValidationError(_('No records selected for transfer.'))
        if not self.dest_location_id:
            raise ValidationError(_('Please select the destination location.'))
        if self.is_bulk and not (self.truck_number or '').strip():
            raise ValidationError(_('Please enter the truck number.'))
        records._check_transfer_ready(bulk=self.is_bulk)
        for rec in records:
            if not rec.product_id:
                raise ValidationError(_('Record %s has no product set.') % rec.name)
            if not rec.quantity or rec.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than 0 (%s).') % rec.name)

        records_by_location = defaultdict(lambda: self.env['livestock.slaugther'])
        for rec in records:
            # the source location: the POS location the animal was sold at
            # (Order Transfer brings it there, Bulk Transfer sends it from there)
            site_loc = rec._slaughter_source_location()
            if site_loc == self.dest_location_id:
                raise ValidationError(_('%s: %s is where the animal already is (or goes). Please select another location.')
                                      % (rec.name, site_loc.display_name))
            records_by_location[site_loc] |= rec

        pickings = self.env['stock.picking']
        for site_loc, location_records in records_by_location.items():
            pickings |= self._create_transfer(site_loc, location_records)

        if self.is_bulk:
            # Print the bulk transfer slip and close the wizard
            action = self.env.ref('bn_livestock_slaugther.action_report_livestock_bulk_transfer').report_action(records)
            action['close_on_report_download'] = True
            return action

        # Open the transfer (one per POS location)
        if len(pickings) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'res_id': pickings.id,
                'target': 'current',
            }
        return {
            'name': _('Transfers'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', pickings.ids)],
            'target': 'current',
        }

    def _create_transfer(self, site_loc, records):
        """One validated picking for ``records`` at ``site_loc``: out of it
        (Bulk Transfer) or into it (Order Transfer)."""
        if self.is_bulk:
            src_loc, dest_loc = site_loc, self.dest_location_id
        else:
            src_loc, dest_loc = self.dest_location_id, site_loc
        # the livestock operation type of the animals' warehouse
        picking_type = self.env['stock.warehouse']._get_program_type('livestock', site_loc)
        if not picking_type:
            raise UserError(_('No internal picking type found. Configure a Warehouse with an Internal Transfers type.'))

        # Build picking
        donees = records.mapped('donee_id')
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': src_loc.id,
            'location_dest_id': dest_loc.id,
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
                'location_dest_id': dest_loc.id,
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

        if self.is_bulk:
            # the source location stays the POS location the record was made with
            records.filtered(lambda r: not r.source_location_id).write({'source_location_id': site_loc.id})
            records.write({
                'transfer_location': self.dest_location_id.id,
                'transfer_picking_id': picking.id,
                'transfer_bool': True,
                'transfer_remarks': self.remarks,
                'truck_number': self.truck_number.strip(),
            })
        else:
            records.write({
                'order_transfer_location_id': self.dest_location_id.id,
                'order_transfer_picking_id': picking.id,
            })
        return picking
