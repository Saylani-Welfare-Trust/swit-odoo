from odoo import models, fields

class ForeignCurrencyWizard(models.TransientModel):
    _name = 'foreign.currency.wizard'
    _description = 'Foreign Currency Wizard'

    line_ids = fields.One2many(
        'foreign.currency.wizard.line',
        'wizard_id',
        string="Lines"
    )

    def action_create_lines(self):
        active_id = self.env.context.get('active_id')
        record = self.env['rider.collection'].browse(active_id)

        for line in self.line_ids:
            self.env['foreign.currency'].create({
                'rider_id': record.rider_id.id,
                'lot_id': record.lot_id.id,
                'amount': line.amount,
                'foreign_notes': line.foreign_notes,
                'rider_log': line.currency,
            })
            
class ForeignCurrencyWizardLine(models.TransientModel):
    _name = 'foreign.currency.wizard.line'
    _description = 'Foreign Currency Wizard Line'

    currency= fields.Char('Currency')
    wizard_id = fields.Many2one('foreign.currency.wizard')
    amount = fields.Float(string="Amount", required=True)
    foreign_notes = fields.Float('Foreign Notes')
