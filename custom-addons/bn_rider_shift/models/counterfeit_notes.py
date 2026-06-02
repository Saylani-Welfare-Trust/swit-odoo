from odoo import api, models, fields
from odoo.exceptions import UserError


class CounterFietNotes(models.Model):
    _name = 'counterfeit.notes'
    _description = "Counterfiet Notes"
    _rec_name = 'rider_name'


    rider_id = fields.Many2one('hr.employee', string="Rider")
    lot_id = fields.Many2one('stock.lot', string="Lot")
    
    rider_name = fields.Char(related='rider_id.name', string="Rider Name", store=True)
    
    submission_time = fields.Date('Submission Date')
    note_type = fields.Selection([
        ('cfb', 'Counterfeit Banknotes (CFB)'),
        ('fcb', 'Foreign Currency Banknotes (FCB)')
    ], string='Note Type', default='cfb', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    amount = fields.Float('Amount')
    state = fields.Selection([('draft', 'Draft'), ('payment_received', 'Payment Received'), ('paid', 'Paid'),('payment_collected', 'Payment Collected'),], string='State', default='draft')

    def action_open_counterfeit_wizard(self):
        if not self:
            raise UserError('Please select counterfeit note records before opening the wizard.')

        invalid_notes = self.filtered(lambda note: note.state != 'draft')
        if invalid_notes:
            raise UserError('Only counterfeit notes in draft state can be selected.')

        if any(not note.lot_id for note in self):
            raise UserError('Selected counterfeit notes must have a box assigned.')

        total_amount = sum(self.mapped('amount'))
        lot_ids = self.mapped('lot_id').ids
        default_lot_id = self[0].lot_id.id if len(set(lot_ids)) == 1 else False
        
        # Check if all notes are same type
        note_types = self.mapped('note_type')
        if len(set(note_types)) > 1:
            raise UserError('All selected notes must be of the same type (CFB or FCB).')

        return {
            'name': 'Create CFB/FCB',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'counterfeit.notes.wizard',
            'target': 'new',
            'context': {
                'default_note_ids': [(6, 0, self.ids)],
                'default_total_amount': total_amount,
                'default_actual_amount': total_amount,
                'default_lot_id': default_lot_id,
                'default_note_type': self[0].note_type if self else 'cfb',
            }
        }