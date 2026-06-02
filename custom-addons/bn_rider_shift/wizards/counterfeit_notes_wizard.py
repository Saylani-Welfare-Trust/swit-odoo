from odoo import models, fields
from odoo.exceptions import UserError


class CounterfeitNotesWizard(models.TransientModel):
    _name = 'counterfeit.notes.wizard'
    _description = 'Counterfeit Notes Wizard'

    note_ids = fields.Many2many(
        'counterfeit.notes',
        'counterfeit_notes_wizard_rel',
        'wizard_id',
        'note_id',
        string='Counterfeit Notes',
    )
    total_amount = fields.Float('Total Amount', readonly=True)
    actual_amount = fields.Float('Actual Amount', required=True)
    lot_id = fields.Many2one('stock.lot', string='Box No.', readonly=True)
    def action_submit_cfb(self):
        notes = self.note_ids
        if not notes:
            notes = self.env['counterfeit.notes'].browse(self.env.context.get('active_ids', []))

        if not notes:
            raise UserError('Please select counterfeit note records before creating CFB.')

        invalid_notes = notes.filtered(lambda note: note.state != 'draft')
        if invalid_notes:
            raise UserError('Only counterfeit notes in draft state can be used.')

        if any(not note.lot_id for note in notes):
            raise UserError('Selected counterfeit notes must have a box assigned.')

        lot_ids = notes.mapped('lot_id').ids
        box = False
        if len(set(lot_ids)) == 1:
            lot = notes[0].lot_id
            box = self.env['donation.box.registration.installation'].search([('lot_id', '=', lot.id)], limit=1)
            if not box:
                raise UserError('Could not find a donation box registration for the selected box.')

        counterfeit_rider = self.env['hr.employee'].search([('name', '=', 'Counterfeit')], limit=1)
        if not counterfeit_rider:
            counterfeit_rider = self.env['hr.employee'].create({'name': 'Counterfeit'})

        # Create the collection first
        collection = self.env['rider.collection'].create({
            'rider_id': counterfeit_rider.id,
            'date': fields.Date.today(),
            'donation_box_registration_installation_id': box.id if box else False,
            'state': 'donation_submit',  # Keep this state
            'amount': self.actual_amount,
            'counterfeit_notes': self.total_amount,
            'remarks': 'CFB',
        })

        # CRITICAL: Create a key issuance record linked to this collection
        # Find or create appropriate key for this box
        key = self.env['key'].search([
            ('donation_box_registration_installation_id', '=', box.id),
            ('state', 'in', ['available', 'issued'])
        ], limit=1)
        
        if not key:
            raise UserError(f'No key found for box {box.name if hasattr(box, "name") else box.id}')

        # Create key issuance record
        key_issuance = self.env['key.issuance'].create({
            'rider_id': counterfeit_rider.id,
            'key_id': key.id,
            'issue_date': fields.Date.today(),
            'issued_on': fields.Datetime.now(),
            'state': 'donation_receive',  # Set to donation_receive state directly for CFB
            'action_type': 'manual',
            'donation_amount': self.actual_amount,
            'rider_collection_id': collection.id,  # If this field exists in key_issuance
        })

        # Update collection with key issuance reference if needed
        if hasattr(collection, 'key_issuance_id'):
            collection.key_issuance_id = key_issuance.id

        notes.write({'state': 'payment_received'})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'CFB Created',
                'message': f'CFB has been created with actual amount {self.actual_amount}. Collection and Key Issuance records have been linked.',
                'type': 'success',
                'sticky': False,
            }
        }