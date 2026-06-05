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
    rider_collection_id = fields.Many2one('rider.collection', string='Rider Collection', ondelete='set null')

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

        # Find or create "Foreign Currency" rider
        fc_rider = self.env['hr.employee'].search([('name', '=', 'Foreign Currency')], limit=1)
        if not fc_rider:
            fc_rider = self.env['hr.employee'].create({'name': 'Foreign Currency'})

        # Find or create a dedicated "Foreign Currency" box registration
        fc_box = self.env['donation.box.registration.installation'].search(
            [('name', 'ilike', 'Foreign Currency')], limit=1
        )
        if not fc_box:
            raise UserError('Could not find a "Foreign Currency" donation box registration. Please create one first.')

        # Create a single rider collection for all selected lines
        rider_collection = self.env['rider.collection'].create({
            'rider_id': fc_rider.id,
            'date': fields.Date.today(),
            'donation_box_registration_installation_id': fc_box.id,
            'state': 'donation_submit',
            'amount': selected_amount,
            'remarks': 'FCB',
        })

        # Link all selected foreign currency lines to this collection
        self.write({'rider_collection_id': rider_collection.id})

        # Create key issuance for the FC box
        key = self.env['key'].search([
            ('donation_box_registration_installation_id', '=', fc_box.id),
            ('state', 'in', ['available', 'issued'])
        ], limit=1)
        if not key:
            key = self.env['key'].search([
                ('donation_box_registration_installation_id', '=', fc_box.id)
            ], limit=1)

        if key:
            key_issuance_vals = {
                'rider_id': fc_rider.id,
                'key_id': key.id,
                'issue_date': fields.Date.today(),
                'issued_on': fields.Datetime.now(),
                'state': 'donation_receive',
                'action_type': 'manual',
                'donation_amount': selected_amount,
            }
            if 'rider_collection_id' in self.env['key.issuance']._fields:
                key_issuance_vals['rider_collection_id'] = rider_collection.id
            self.env['key.issuance'].create(key_issuance_vals)

        # Update state for all selected lines
        self.write({'state': 'payment_received'})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'FCB Created',
                'message': f'FCB collection created with total amount {selected_amount}. Please collect payment from POS.',
                'type': 'success',
                'sticky': False,
            }
        }
    def action_create_donation_box_request(self):
        """Compatibility wrapper for legacy donation-box button calls."""
        return self.action_create_pos_record()
