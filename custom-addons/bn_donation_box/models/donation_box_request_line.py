from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class DonationBoxRequestLine(models.Model):
    _name = 'donation.box.request.line'
    _description = 'Donation Box Request Line'


    donation_box_request_id = fields.Many2one('donation.box.request', string="Donation Box Request")
    product_id = fields.Many2one('product.product', string="Product")
    lot_id = fields.Many2one('stock.lot', string="Lot")

    used = fields.Boolean('Used in Picking', default=False)

    lock_no = fields.Char('Lock No.')
    key_tag = fields.Char('Key Tag')
    old_box_no = fields.Char('Old Box No.')

    allowed_lot_ids = fields.Many2many(
        'stock.lot',
        string="Allowed Lots",
        compute="_compute_allowed_lot_ids",
        store=False
    )
    

    @api.depends('product_id', 'donation_box_request_id.source_location_id')
    def _compute_allowed_lot_ids(self):
        for line in self:
            if not line.product_id or not line.donation_box_request_id.source_location_id:
                line.allowed_lot_ids = [(5, 0, 0)]  # empty domain
                continue

            lots = self.env['stock.lot'].search([
                ('product_id', '=', line.product_id.id),
                # ('product_qty', '>', 0),
                ('location_id', '=', line.donation_box_request_id.source_location_id.id),
            ])

            lot_ids = lots.filtered(lambda l: not l.lot_consume)
            line.allowed_lot_ids = lot_ids

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('key_tag'):
                vals['key_tag'] = self.env['ir.sequence'].next_by_code('donation_box_key') or 'Unknown'

        return super(DonationBoxRequestLine, self).create(vals_list)

    def action_draft_line(self):
        """
        Reset a single donation box request line to draft state.
        This removes the line and its associated records.
        """
        
        for line in self:
            parent_request = line.donation_box_request_id
            
            # Get registration/installation records for this specific line
            line_registration_records = parent_request.donation_box_registration_installation_ids.filtered(
                lambda r: r.lot_id.id == line.lot_id.id
            )
            
            if not line_registration_records:
                raise ValidationError("No installation records found for this line.")
            
            # Check if any are installed
            installed_records = line_registration_records.filtered(lambda r: r.box_status == 'installed')
            
            if installed_records:
                raise ValidationError(
                    "Cannot reset this line because the donation box is already installed."
                )
            
            # Reset the lot
            if line.lot_id:
                line.lot_id.write({
                    'lot_consume': False,
                    'location_id': parent_request.source_location_id.id
                })
            
            # Delete keys associated with this line
            self.env['key'].search([
                ('lot_id', '=', line.lot_id.id),
                ('donation_box_request_id', '=', parent_request.id)
            ]).unlink()
            
            # Delete registration/installation records for this line
            line_registration_records.unlink()
            
            # Delete the line itself
            line.unlink()