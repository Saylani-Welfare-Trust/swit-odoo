from odoo import models, fields


class CounterFietNotes(models.Model):
    _name = 'counterfeit.notes'
    _description = "Counterfiet Notes"


    rider_id = fields.Many2one('hr.employee', string="Rider")
    lot_id = fields.Many2one('stock.lot', string="Lot")
    
    submission_time = fields.Date('Submission Date')

    amount = fields.Float('Amount')