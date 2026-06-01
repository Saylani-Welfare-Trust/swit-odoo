from odoo import models, fields
from odoo.exceptions import UserError


state_selection = [
    ('draft', 'Draft'),
    ('converted', 'Converted'),
    ('reject', 'Reject'),
]


class ForeignCurrency(models.Model):
    _name = 'foreign.currency'
    _description = "Foreign Currency"


    currency_id = fields.Many2one('res.currency', string="Currency")
    
    rider_log = fields.Char('Currency')

    amount = fields.Float('Amount')
    foreign_notes = fields.Float('Foreign Notes')
    exchanged_amount = fields.Float('Exchanged Amount')
    conversion_rate = fields.Float('Conversion Rate', default=1.0)

    rider_id = fields.Many2one('hr.employee', string="Rider")
    lot_id = fields.Many2one('stock.lot', string="Lot")

    state = fields.Selection(selection=state_selection, string="State", default='draft')
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")


    def action_convert_amount(self):
        self.exchanged_amount = self.amount * self.conversion_rate
        self.state = 'converted'

    def action_reject(self):
        self.state = 'reject'

    def action_create_pos_record(self):
        """Create a POS order for the selected foreign currency lines."""
        if 'pos.order' not in self.env:
            raise UserError('POS module is not available in this database.')

        invalid_lines = self.filtered(lambda rec: rec.state != 'converted')
        if invalid_lines:
            raise UserError('Only converted foreign currency lines can be used. Please select only converted lines.')

        selected_amount = sum(self.mapped('exchanged_amount'))
        if not selected_amount:
            raise UserError('Please select converted foreign currency lines with a non-zero exchanged amount.')

        if any(not rec.rider_id for rec in self):
            raise UserError('Selected foreign currency lines must have a rider assigned.')
        rider_ids = self.mapped('rider_id')
        if len(rider_ids) != 1:
            raise UserError('Selected foreign currency lines must belong to the same rider.')

        if any(not rec.lot_id for rec in self):
            raise UserError('Selected foreign currency lines must have a box assigned.')
        lot_ids = self.mapped('lot_id')
        if len(lot_ids) != 1:
            raise UserError('Selected foreign currency lines must belong to the same box.')

        rider = rider_ids[0]
        lot = lot_ids[0]

        box = self.env['donation.box.registration.installation'].search([('lot_id', '=', lot.id)], limit=1)
        if not box:
            raise UserError('Could not find a donation box registration for the selected box.')

        rider_collection = self.env['rider.collection'].search([
            ('rider_id', '=', rider.id),
            ('donation_box_registration_installation_id', '=', box.id),
            ('date', '=', fields.Date.today()),
        ], limit=1)
        if rider_collection:
            rider_collection.amount += selected_amount
        else:
            rider_collection = self.env['rider.collection'].create({
                'rider_id': rider.id,
                'date': fields.Date.today(),
                'donation_box_registration_installation_id': box.id,
                'state': 'donation_not_collected',
                'amount': selected_amount,
            })

        session = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
        if not session:
            session = self.env['pos.session'].search([], limit=1)
        if not session:
            raise UserError('No POS session available to create a POS order.')

        product = self.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        if not product:
            product = self.env['product.product'].search([], limit=1)
        if not product:
            raise UserError('No product found to create POS order lines.')

        current_time = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        pos_name = f"FCB-{current_time.strftime('%Y%m%d%H%M%S')}"

        order_vals = {
            'name': pos_name,
            'session_id': session.id,
            'user_id': session.user_id.id or self.env.uid,
            'state': 'draft',
            'amount_total': selected_amount,
            'amount_tax': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'lines': [(0, 0, {
                'product_id': product.id,
                'name': f'{pos_name} total',
                'qty': 1,
                'price_unit': selected_amount,
                'price_subtotal': selected_amount,
                'price_subtotal_incl': selected_amount,
            })],
        }

        if 'pos_order_seq' in self.env['pos.order']._fields:
            order_vals['pos_order_seq'] = pos_name
        if 'source_document' in self.env['pos.order']._fields:
            order_vals['source_document'] = pos_name
        pos_order = self.env['pos.order'].create(order_vals)

        return {
            'name': 'POS Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'res_id': pos_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_donation_box_request(self):
        """Compatibility wrapper for legacy donation-box button calls."""
        return self.action_create_pos_record()
