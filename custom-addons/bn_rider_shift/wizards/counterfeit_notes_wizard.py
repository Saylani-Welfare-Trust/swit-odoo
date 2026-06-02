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

        # Don't require all notes to be from same box - allow multiple boxes
        # Just get all unique lots/boxes from the selected notes
        unique_lots = notes.mapped('lot_id')
        unique_boxes = self.env['donation.box.registration.installation'].search([
            ('lot_id', 'in', unique_lots.ids)
        ])
        
        if not unique_boxes:
            raise UserError('Could not find donation box registrations for the selected boxes.')

        counterfeit_rider = self.env['hr.employee'].search([('name', '=', 'Counterfeit')], limit=1)
        if not counterfeit_rider:
            counterfeit_rider = self.env['hr.employee'].create({'name': 'Counterfeit'})

        # Create ONE collection for all counterfeit notes (consolidated)
        # Note: We're not linking to a specific donation_box_registration_installation_id
        # since notes come from multiple boxes
        collection = self.env['rider.collection'].create({
            'rider_id': counterfeit_rider.id,
            'date': fields.Date.today(),
            'donation_box_registration_installation_id': False,  # No single box since multiple boxes
            'state': 'donation_submit',
            'amount': self.actual_amount,
            'counterfeit_notes': self.total_amount,
            'remarks': 'CFB - Multiple Boxes',
        })

        # Create key issuance records for EACH box separately
        key_issuance_ids = []
        for box in unique_boxes:
            # Find key for this box
            key = self.env['key'].search([
                ('donation_box_registration_installation_id', '=', box.id),
                ('state', 'in', ['available', 'issued'])
            ], limit=1)
            
            if not key:
                key = self.env['key'].search([
                    ('donation_box_registration_installation_id', '=', box.id)
                ], limit=1)
                
                if not key:
                    _logger.warning(f'No key found for donation box {box.id}. Skipping key issuance for this box.')
                    continue

            # Create key issuance record for this box
            key_issuance_vals = {
                'rider_id': counterfeit_rider.id,
                'key_id': key.id,
                'issue_date': fields.Date.today(),
                'issued_on': fields.Datetime.now(),
                'state': 'donation_receive',
                'action_type': 'manual',
                'donation_amount': self.actual_amount / len(unique_boxes) if len(unique_boxes) > 1 else self.actual_amount,  # Split amount across boxes or use full amount
            }
            
            # Add rider_collection_id if the field exists
            if 'rider_collection_id' in self.env['key.issuance']._fields:
                key_issuance_vals['rider_collection_id'] = collection.id
            
            key_issuance = self.env['key.issuance'].create(key_issuance_vals)
            key_issuance_ids.append(key_issuance.id)

        # Mark all counterfeit notes as payment_received
        notes.write({'state': 'payment_received'})

        # Prepare success message
        message = f'CFB has been created with actual amount {self.actual_amount}. '
        message += f'Processed {len(notes)} counterfeit notes from {len(unique_boxes)} box(es).'
        if key_issuance_ids:
            message += f' Created {len(key_issuance_ids)} key issuance record(s).'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'CFB Created',
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }