from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class LivestockSlaugtherWizard(models.TransientModel):
    _name = 'livestock.slaugther.wizard'
    _description = "Livestock Slaugther Wizard"


    dest_location_id = fields.Many2one('stock.location', string='Destination Location')
    livestock_slaughter_id = fields.Many2one('livestock.slaugther', string='Livestock Slaugther')
    line_ids = fields.One2many('livestock.slaugther.wizard.line', 'wizard_id', string='Lines')
    remarks = fields.Text('Remarks')
    is_bulk = fields.Boolean('Bulk Transfer')
    total_quantity = fields.Integer('Total Quantity', compute='_compute_total_quantity')

    @api.depends('line_ids.quantity')
    def _compute_total_quantity(self):
        for wizard in self:
            wizard.total_quantity = sum(wizard.line_ids.mapped('quantity'))

    @api.model
    def _open_for(self, records, title, is_bulk=False):
        """Create the wizard for the given slaughter records, with the source
        location of each line set to where its product currently is."""
        sources = records._suggest_source_locations()
        wizard = self.create({
            'livestock_slaughter_id': records[:1].id if not is_bulk else False,
            'is_bulk': is_bulk,
            'line_ids': [(0, 0, {
                'slaughter_id': rec.id,
                'source_location_id': sources.get(rec.id),
            }) for rec in records],
        })
        return {
            'name': title,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            # the Slaugther menu action has edit=0, which would open this wizard readonly
            'context': {'edit': True},
        }

    def action_do_transfer(self):
        """Create an internal picking from each line's source location to the
        chosen destination, move the product and quantity of every selected
        slaughter record and validate it."""
        self.ensure_one()
        lines = self.line_ids
        records = lines.mapped('slaughter_id')

        # basic validations
        if not lines:
            raise ValidationError(_('No records selected for transfer.'))
        if not self.dest_location_id:
            raise ValidationError(_('Please select the destination location.'))
        transferred = records.filtered('transfer_bool')
        if transferred:
            raise ValidationError(_('Already transferred: %s') % ', '.join(transferred.mapped('name')))
        for line in lines:
            rec = line.slaughter_id
            if not rec.product_id:
                raise ValidationError(_('Record %s has no product set.') % rec.name)
            if not rec.quantity or rec.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than 0 (%s).') % rec.name)
            if not line.source_location_id:
                raise ValidationError(_('Please select the source location for %s (%s).') % (rec.name, rec.product_id.display_name))
            if line.source_location_id == self.dest_location_id:
                raise ValidationError(_('Source and destination location are the same for %s.') % rec.name)

        # choose internal picking type for the company (fallback to any internal if company-specific not found)
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
        if not picking_type:
            raise UserError(_('No internal picking type found. Configure a Warehouse with an Internal Transfers type.'))

        # one picking per source location
        pickings = self.env['stock.picking']
        for src_loc in lines.mapped('source_location_id'):
            src_lines = lines.filtered(lambda l: l.source_location_id == src_loc)
            src_records = src_lines.mapped('slaughter_id')

            donees = src_records.mapped('donee_id')
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': src_loc.id,
                'location_dest_id': self.dest_location_id.id,
                'partner_id': donees.id if len(donees) == 1 else False,
                'origin': ', '.join(src_records.mapped('name')) or _('Slaughter Transfer'),
                'note': self.remarks or False,
                'company_id': self.env.company.id,
            })

            # Build one move per record
            for rec in src_records:
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

            src_records.write({
                'source_location_id': src_loc.id,
                'transfer_location': self.dest_location_id.id,
                'transfer_picking_id': picking.id,
                'transfer_remarks': self.remarks or False,
                'transfer_bool': True,
            })
            pickings |= picking

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
            'res_id': pickings[:1].id,
            'target': 'current',
        }


class LivestockSlaugtherWizardLine(models.TransientModel):
    _name = 'livestock.slaugther.wizard.line'
    _description = "Livestock Slaugther Wizard Line"


    wizard_id = fields.Many2one('livestock.slaugther.wizard', string='Wizard', required=True, ondelete='cascade')
    slaughter_id = fields.Many2one('livestock.slaugther', string='Reference', required=True)
    product_id = fields.Many2one(related='slaughter_id.product_id')
    donee_id = fields.Many2one(related='slaughter_id.donee_id')
    ref = fields.Char(related='slaughter_id.ref')
    quantity = fields.Integer(related='slaughter_id.quantity')
    source_location_id = fields.Many2one(
        'stock.location', string='Source Location',
        domain="[('usage', 'in', ['internal', 'transit'])]",
    )
    available_qty = fields.Float('Available at Source', compute='_compute_available_qty')

    @api.depends('product_id', 'source_location_id')
    def _compute_available_qty(self):
        for line in self:
            if line.product_id and line.source_location_id:
                line.available_qty = line.product_id.with_context(location=line.source_location_id.id).qty_available
            else:
                line.available_qty = 0.0
