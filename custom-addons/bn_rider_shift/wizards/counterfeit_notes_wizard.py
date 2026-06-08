from odoo import models, fields
from odoo.exceptions import UserError
import logging


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

        counterfeit_rider = self.env['hr.employee'].search([('name', '=', 'Counterfeit')], limit=1)
        if not counterfeit_rider:
            counterfeit_rider = self.env['hr.employee'].create({'name': 'Counterfeit'})

        # Create collection with links to counterfeit notes
        collection = self.env['rider.collection'].create({
            'rider_id': counterfeit_rider.id,
            'date': fields.Date.today(),
            'state': 'donation_submit',
            'amount': self.actual_amount,
            'counterfeit_notes': self.total_amount,
            'remarks': 'CFB',
            'counterfeit_note_ids': [(6, 0, notes.ids)],
        })

        # Get all unique boxes/lots from selected notes
        unique_lots = notes.mapped('lot_id')
        unique_boxes = self.env['donation.box.registration.installation'].search([
            ('lot_id', 'in', unique_lots.ids)
        ])

        # Create key issuance for each box
        for box in unique_boxes:
            key = self.env['key'].search([
                ('donation_box_registration_installation_id', '=', box.id),
                ('state', 'in', ['available', 'issued'])
            ], limit=1)
            
            if not key:
                key = self.env['key'].search([
                    ('donation_box_registration_installation_id', '=', box.id)
                ], limit=1)
                
                if not key:
                    raise UserError(f'No key found for donation box {box.id}')
                    continue

            key_issuance_vals = {
                'rider_id': counterfeit_rider.id,
                'key_id': key.id,
                'issue_date': fields.Date.today(),
                'issued_on': fields.Datetime.now(),
                'state': 'donation_receive',
                'action_type': 'manual',
                'donation_amount': self.actual_amount,
            }
            
            if 'rider_collection_id' in self.env['key.issuance']._fields:
                key_issuance_vals['rider_collection_id'] = collection.id
            
            self.env['key.issuance'].create(key_issuance_vals)

        # IMPORTANT: Do NOT change note state here
        # Notes will be updated to 'paid' when POS collects payment
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'CFB Created',
                'message': f'CFB collection created. Please collect payment of {self.actual_amount} from POS to complete the process.',
                'type': 'success',
                'sticky': False,
            }
        }