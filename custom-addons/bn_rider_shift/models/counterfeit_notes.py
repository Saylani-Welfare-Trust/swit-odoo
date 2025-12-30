from odoo import models, fields


class CounterFietNotes(models.Model):
    _name = 'counterfeit.notes'
    _description = "Counterfiet Notes"
    _rec_name = 'rider_name'


    rider_id = fields.Many2one('hr.employee', string="Rider")
    lot_id = fields.Many2one('stock.lot', string="Lot")
    
    rider_name = fields.Char(related='rider_id.name', string="Rider Name", store=True)
    
    submission_time = fields.Date('Submission Date')

    amount = fields.Float('Amount')