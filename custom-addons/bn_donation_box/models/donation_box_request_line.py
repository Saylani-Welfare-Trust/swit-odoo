from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class DonationBoxRequestLine(models.Model):
    _name = 'donation.box.request.line'
    _description = 'Donation Box Request Line'

    donation_box_request_id = fields.Many2one('donation.box.request', string="Donation Box Request")
    product_id = fields.Many2one('product.product', string="Product")
    lot_id = fields.Many2one('stock.lot', string="Lot")

    lock_no = fields.Char('Lock No.')
    key_tag = fields.Char('Key Tag')
    old_box_no = fields.Char('Old Box No.')

    allowed_lot_ids = fields.Many2many(
        'stock.lot',
        string="Allowed Lots",
        compute="_compute_allowed_lot_ids",
        store=False
    )

    on_hand_qty = fields.Float(
        string="On Hand Qty",
        compute="_compute_on_hand_qty",
        store=False
    )

    @api.depends('product_id', 'donation_box_request_id.source_location_id')
    def _compute_on_hand_qty(self):
        for line in self:
            if not line.product_id or not line.donation_box_request_id.source_location_id:
                line.on_hand_qty = 0.0
                continue

            quants = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', line.donation_box_request_id.source_location_id.id),
            ])
            line.on_hand_qty = sum(quants.mapped('quantity'))

    @api.depends('product_id', 'donation_box_request_id.source_location_id')
    def _compute_allowed_lot_ids(self):
        for line in self:
            if not line.product_id or not line.donation_box_request_id.source_location_id:
                line.allowed_lot_ids = [(5, 0, 0)]
                continue

            lots = self.env['stock.lot'].search([
                ('product_id', '=', line.product_id.id),
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
        for line in self:
            parent_request = line.donation_box_request_id

            line_registration_records = parent_request.donation_box_registration_installation_ids.filtered(
                lambda r: r.lot_id.id == line.lot_id.id
            )

            if not line_registration_records:
                raise ValidationError("No installation records found for this line.")

            installed_records = line_registration_records.filtered(lambda r: r.box_status == 'installed')

            if installed_records:
                raise ValidationError(
                    "Cannot reset this line because the donation box is already installed."
                )

            if line.lot_id:
                line.lot_id.write({
                    'lot_consume': False,
                    'location_id': parent_request.source_location_id.id
                })

            self.env['key'].search([
                ('lot_id', '=', line.lot_id.id),
                ('donation_box_request_id', '=', parent_request.id)
            ]).unlink()

            line_registration_records.unlink()
            line.unlink()