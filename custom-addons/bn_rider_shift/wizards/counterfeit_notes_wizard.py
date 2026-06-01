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

        self.env['rider.collection'].create({
            'rider_id': counterfeit_rider.id,
            'date': fields.Date.today(),
            'donation_box_registration_installation_id': box.id,
            'state': 'donation_submit',
            'amount': self.actual_amount,
            'counterfeit_notes': self.total_amount,
            'remarks': 'CFB',
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'CFB Created',
                'message': f'CFB has been created with actual amount {self.actual_amount}.',
                'type': 'success',
                'sticky': False,
            }
        }
