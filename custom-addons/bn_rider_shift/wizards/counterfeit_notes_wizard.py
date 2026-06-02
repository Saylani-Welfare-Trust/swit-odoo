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
        else:
            raise UserError('All selected counterfeit notes must belong to the same box/lot.')

        counterfeit_rider = self.env['hr.employee'].search([('name', '=', 'Counterfeit')], limit=1)
        if not counterfeit_rider:
            counterfeit_rider = self.env['hr.employee'].create({'name': 'Counterfeit'})

        # Create the collection first
        collection = self.env['rider.collection'].create({
            'rider_id': counterfeit_rider.id,
            'date': fields.Date.today(),
            'donation_box_registration_installation_id': box.id,
            'state': 'donation_submit',
            'amount': self.actual_amount,
            'counterfeit_notes': self.total_amount,
            'remarks': 'CFB',
        })

        # Find key for this box - ONLY if box exists (which it does at this point)
        key = self.env['key'].search([
            ('donation_box_registration_installation_id', '=', box.id),
            ('state', 'in', ['available', 'issued'])
        ], limit=1)
        
        if not key:
            # Try to find any key associated with this box without state restriction
            key = self.env['key'].search([
                ('donation_box_registration_installation_id', '=', box.id)
            ], limit=1)
            
            if not key:
                # Instead of raising error, log warning but continue
                _logger.warning(f'No key found for donation box {box.id}. CFB collection created without key issuance.')
                notes.write({'state': 'payment_received'})
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'CFB Created',
                        'message': f'CFB has been created with actual amount {self.actual_amount}. Note: No key found for this box.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

        # Create key issuance record
        key_issuance_vals = {
            'rider_id': counterfeit_rider.id,
            'key_id': key.id,
            'issue_date': fields.Date.today(),
            'issued_on': fields.Datetime.now(),
            'state': 'donation_receive',
            'action_type': 'manual',
            'donation_amount': self.actual_amount,
        }
        
        # Add rider_collection_id if the field exists
        if 'rider_collection_id' in self.env['key.issuance']._fields:
            key_issuance_vals['rider_collection_id'] = collection.id
        
        key_issuance = self.env['key.issuance'].create(key_issuance_vals)

        # Update collection with key issuance reference if the field exists
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