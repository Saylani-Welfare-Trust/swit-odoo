from odoo import _, models, fields
from odoo.exceptions import AccessError, UserError

EDIT_AMOUNT_GROUP = 'bn_rider_shift.group_foreign_currency_collection'


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
    
    rider_log = fields.Char('Rider Log Currency')

    amount = fields.Float('Amount')
    foreign_notes = fields.Float('Foreign Notes')
    exchanged_amount = fields.Float('Exchanged Amount')
    conversion_rate = fields.Float('Conversion Rate', default=1.0)

    rider_id = fields.Many2one('hr.employee', string="Rider")
    lot_id = fields.Many2one('stock.lot', string="Lot")

    state = fields.Selection(selection=state_selection, string="State", default='draft', index=True)
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    rider_collection_id = fields.Many2one('rider.collection', string='Rider Collection', ondelete='set null')

    def write(self, vals):
        if not self.env.su and 'amount' in vals and not self.env.user.has_group(EDIT_AMOUNT_GROUP):
            raise UserError(
                "You are not allowed to edit the Amount of a Foreign Currency line. "
                "Required access group: Foreign Currency Collection."
            )
        return super().write(vals)

    def _check_draft(self, action):
        # once converted, the amount is what the POS donation box (FCB) is paid with
        if self.filtered(lambda rec: rec.state != 'draft'):
            raise UserError(_('Only Draft foreign currency can be %s.') % action)

    def action_convert_amount(self):
        self._check_draft(_('converted'))
        for rec in self:
            rec.write({'exchanged_amount': rec.amount * rec.conversion_rate, 'state': 'converted'})

    def action_reject(self):
        self._check_draft(_('rejected'))
        self.write({'state': 'reject'})

    def action_create_pos_record(self):
        """Create a donation box (FCB) from selected foreign currency lines."""
        # the button is the Foreign Currency Collection group's: also refused over RPC
        if not self.env.su and not self.env.user.has_group(EDIT_AMOUNT_GROUP):
            raise AccessError(_('Only the Foreign Currency Collection group can create the POS record.'))
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
        fc_rider = self.env['hr.employee'].sudo().search([('name', '=', 'Foreign Currency')], limit=1)
        if not fc_rider:
            fc_rider = self.env['hr.employee'].sudo().create({
                'name': 'Foreign Currency',
            })

        # Find the donation box registration for this lot
        # The registration in service wins over closed ones of a reused box number.
        box = self.env['donation.box.registration.installation'].sudo()._find_by_lot(lot)
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
        })

        # Link the foreign currency lines to this collection
        self.write({'rider_collection_id': rider_collection.id})

        # Create key issuance for this box
        key = self.env['key'].sudo().search([
            ('donation_box_registration_installation_id', '=', box.id),
            ('state', 'in', ['available', 'issued'])
        ], limit=1)
        
        if not key:
            key = self.env['key'].sudo().search([
                ('donation_box_registration_installation_id', '=', box.id)
            ], limit=1)

        if key:
            if key.state != 'available':
                raise UserError(
                    f'Key "{key.name}" is not Available (current status: {key.state}); '
                    'cannot create an FCB issuance for it.'
                )
            key._lock_key()
            # Keep key.state consistent with the issuance created below - money is
            # already collected (via currency conversion), so the key goes straight
            # to Issued and the issuance record starts at "Donation Received".
            key._workflow_write({'state': 'issued'})

            key_issuance_vals = {
                'rider_id': fc_rider.id,
                'key_id': key.id,
                'issue_date': fields.Date.today(),
                'issued_on': fields.Datetime.now(),
                'state': 'donation_receive',
                'action_type': 'manual',
                'donation_amount': selected_amount,
                'is_fcb': True,
                'rider_collection_id': rider_collection.id,
            }
            self.env['key.issuance'].sudo().create(key_issuance_vals)

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
