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
        """Create a donation box (FCB) from selected foreign currency lines."""
        # Validate selected lines
        invalid_lines = self.filtered(lambda rec: rec.state != 'converted')
        if invalid_lines:
            raise UserError('Only converted foreign currency lines can be used. Please select only converted lines.')

        selected_amount = sum(self.mapped('exchanged_amount'))
        if not selected_amount:
            raise UserError('Please select converted foreign currency lines with a non-zero exchanged amount.')

        if any(not rec.lot_id for rec in self):
            raise UserError('Selected foreign currency lines must have a box assigned.')
        lot_ids = self.mapped('lot_id')
        if len(lot_ids) != 1:
            raise UserError('Selected foreign currency lines must belong to the same box.')

        lot = lot_ids[0]

        # Find or create "Foreign Currency" rider
        fc_rider = self.env['hr.employee'].search([('name', '=', 'Foreign Currency')], limit=1)
        if not fc_rider:
            fc_rider = self.env['hr.employee'].create({
                'name': 'Foreign Currency',
            })

        # Create FCB donation box
        current_time = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        fcb_name = f"FCB-{current_time.strftime('%Y%m%d%H%M%S')}"

        # Find the donation box registration for this lot
        box = self.env['donation.box.registration.installation'].search([('lot_id', '=', lot.id)], limit=1)
        if not box:
            raise UserError('Could not find a donation box registration for the selected box.')

        # Create rider collection with FCB name
        rider_collection = self.env['rider.collection'].create({
            'rider_id': fc_rider.id,
            'date': fields.Date.today(),
            'donation_box_registration_installation_id': box.id,
            'state': 'donation_not_collected',
            'amount': selected_amount,
            'remarks': fcb_name,  # Store FCB name in remarks
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'FCB Box Created',
                'message': f'{fcb_name} box created with amount {selected_amount}. It will appear under "Foreign Currency" rider in POS.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_create_donation_box_request(self):
        """Compatibility wrapper for legacy donation-box button calls."""
        return self.action_create_pos_record()
