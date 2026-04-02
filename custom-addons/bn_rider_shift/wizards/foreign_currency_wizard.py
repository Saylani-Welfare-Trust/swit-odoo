from odoo import models, fields

class ForeignCurrencyWizard(models.TransientModel):
    _name = 'foreign.currency.wizard'
    _description = 'Foreign Currency Wizard'

    line_count = fields.Integer(string="Number of Lines", required=True)
    line_ids = fields.One2many(
        'foreign.currency.wizard.line',
        'wizard_id',
        string="Lines"
    )

    # def action_generate_lines(self):
    #     # clear old lines
    #     self.line_ids.unlink()

    #     lines = []
    #     for i in range(self.line_count):
    #         lines.append((0, 0, {
    #             'amount': 0.0
    #         }))

    #     self.line_ids = lines

    def action_create_lines(self):
        active_id = self.env.context.get('active_id')
        record = self.env['rider.collection'].browse(active_id)

        for line in self.line_ids:
            self.env['foreign.currency'].create({
                'rider_id': record.rider_id.id,
                'lot_id': record.lot_id.id,
                'amount': line.amount,
                'foreign_notes': record.foreign_notes,
            })
            
class ForeignCurrencyWizardLine(models.TransientModel):
    _name = 'foreign.currency.wizard.line'
    _description = 'Foreign Currency Wizard Line'

    wizard_id = fields.Many2one('foreign.currency.wizard')
    amount = fields.Float(string="Amount", required=True)