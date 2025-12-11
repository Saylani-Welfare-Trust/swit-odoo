from odoo import models, fields, api, _


state_selection = [
    ('unpaid', 'Unpaid'),
    ('partial', 'Partial'),
    ('paid', 'Paid')
]


class MicrofinanceRecoveryLine(models.Model):
    _name = 'microfinance.recovery.line'
    _description = "Microfinance Recovery Line"


    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    
    name = fields.Char('Name', default="NEW")
    installment_no = fields.Char('Installment No.')

    due_date = fields.Date('Due Date')
    
    amount = fields.Monetary('Amount', currency_field='currency_id', default=0)
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id', default=0)
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_remaining_amount', store=True)

    currency_id = fields.Many2one(related='microfinance_id.currency_id', string="Currency")

    state = fields.Selection(selection=state_selection, string='State')


    @api.model
    def create(self, vals):
        if vals.get('name', _('NEW') == _('NEW')):
            vals['name'] = self.env['ir.sequence'].next_by_code('microfinance_recovery_line') or ('New')
                
        return super(MicrofinanceRecoveryLine, self).create(vals)
    
    @api.depends('due_date')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.amount - rec.paid_amount