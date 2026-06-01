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

    amount = fields.Float('Amount')

    def action_open_counterfeit_wizard(self):
        if not self:
            raise UserError('Please select counterfeit note records before opening the wizard.')

        if any(not note.lot_id for note in self):
            raise UserError('Selected counterfeit notes must have a box assigned.')
        if len(self.mapped('lot_id')) != 1:
            raise UserError('Selected counterfeit notes must belong to the same box.')

        total_amount = sum(self.mapped('amount'))
        lot = self[0].lot_id

        return {
            'name': 'Create CFB',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'counterfeit.notes.wizard',
            'target': 'new',
            'context': {
                'default_note_ids': [(6, 0, self.ids)],
                'default_total_amount': total_amount,
                'default_actual_amount': total_amount,
                'default_lot_id': lot.id,
            }
        }
