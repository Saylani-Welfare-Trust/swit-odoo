from odoo import models, fields
from odoo.exceptions import UserError


state_selection = [
    ('draft', 'Draft'),
    ('converted', 'Converted'),
    ('reject', 'Reject'),
    ('payment_received', 'Payment Received'), 
    ('paid', 'Paid'), 
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

        # Find the donation box registration for this lot
        box = self.env['donation.box.registration.installation'].search([('lot_id', '=', lot.id)], limit=1)
        if not box:
            raise UserError('Could not find a donation box registration for the selected box.')

        # Create rider collection with FCB remarks
        rider_collection = self.env['rider.collection'].create({
            'rider_id': fc_rider.id,
            'date': fields.Date.today(),
            'donation_box_registration_installation_id': box.id,
            'state': 'donation_submit',
            'amount': selected_amount,
            'remarks': 'FCB',  # Use 'FCB' as remarks to identify in POS
            'foreign_currency_line_ids': [(6, 0, self.ids)],  # Link to foreign currency lines
        })

        # Create key issuance for this box
        key = self.env['key'].search([
            ('donation_box_registration_installation_id', '=', box.id),
            ('state', 'in', ['available', 'issued'])
        ], limit=1)
        
        if not key:
            key = self.env['key'].search([
                ('donation_box_registration_installation_id', '=', box.id)
            ], limit=1)

        if key:
            key_issuance = self.env['key.issuance'].create({
                'rider_id': fc_rider.id,
                'key_id': key.id,
                'issue_date': fields.Date.today(),
                'issued_on': fields.Datetime.now(),
                'state': 'donation_receive',
                'action_type': 'manual',
                'donation_amount': selected_amount,
                'is_fcb': True,  # Flag for FCB
            })
            
            # Link key issuance to collection if field exists
            if 'rider_collection_id' in self.env['key.issuance']._fields:
                key_issuance.rider_collection_id = rider_collection.id

        # CHANGE STATE TO PAYMENT_RECEIVED
        self.write({'state': 'payment_received'})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'FCB Created',
                'message': f'FCB collection created with amount {selected_amount}. Please collect payment from POS.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_create_donation_box_request(self):
        """Compatibility wrapper for legacy donation-box button calls."""
        return self.action_create_pos_record()
