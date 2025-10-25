from odoo import models, fields, api


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

            quants = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('lot_id', '!=', False),
                ('quantity', '>', 0),
                ('location_id', '=', line.donation_box_request_id.source_location_id.id),
            ])

            lot_ids = quants.mapped('lot_id').filtered(lambda l: not l.lot_consume)
            line.allowed_lot_ids = lot_ids

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('key_tag'):
                vals['key_tag'] = self.env['ir.sequence'].next_by_code('donation_box_key') or 'Unknown'

        return super(DonationBoxRequestLine, self).create(vals_list)