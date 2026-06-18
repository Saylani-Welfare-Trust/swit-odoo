from odoo import models, fields, api, _

state_cheque_selection = [
    ('draft', 'Draft'),
    ('deposited', 'Deposited'),
    ('cleared', 'Cleared'),
    ('bounced', 'Bounced')
]

class MicrofinancePDCLine(models.Model):
    _name = 'microfinance.pdc.line'
    _description = "Microfinance PDC Line"
    _rec_name = 'installment_number'

    microfinance_id = fields.Many2one('microfinance', string="Microfinance", required=True, ondelete='cascade')
    microfinance_line_id = fields.Many2one('microfinance.line', string="Microfinance Line", ondelete='set null')
    donee_id = fields.Many2one('res.partner', string='Donee Name', related='microfinance_line_id.donee_id', store=True)
    installment_number = fields.Char('Installment Number')
    cheque_date = fields.Date('Cheque Date')
    bank_name = fields.Char('Bank Name')
    cheque_no = fields.Char('Cheque No.')
    amount_total = fields.Monetary('Amount Total', currency_field='currency_id')
    state_cheque = fields.Selection(selection=state_cheque_selection, string='Cheque Status', default='draft')
    is_cheque_deposit = fields.Boolean('Is Cheque Deposit', default=False)
    currency_id = fields.Many2one('res.currency', related='microfinance_id.currency_id', string="Currency")
    
    # For POS integration
    pos_cheque_id = fields.Many2one('pos.cheque', string="POS Cheque")
    
    # For tracking
    created_by = fields.Many2one('res.users', string="Created By", default=lambda self: self.env.user)
    create_date = fields.Datetime('Created Date', default=fields.Datetime.now)

    @api.model
    def create(self, vals):
        if not vals.get('installment_number') and vals.get('microfinance_line_id'):
            line = self.env['microfinance.line'].browse(vals['microfinance_line_id'])
            if line:
                vals['installment_number'] = line.installment_no or line.installment_number

        # AUTO-LINK via installment_number instead of cheque_no
        if not vals.get('microfinance_line_id') and vals.get('installment_number') and vals.get('microfinance_id'):
            microfinance_line = self.env['microfinance.line'].search([
                ('microfinance_id', '=', vals['microfinance_id']),
                ('installment_no', '=', vals['installment_number']),
            ], limit=1)
            if microfinance_line:
                vals['microfinance_line_id'] = microfinance_line.id

        return super(MicrofinancePDCLine, self).create(vals)