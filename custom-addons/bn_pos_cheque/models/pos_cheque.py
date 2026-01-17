from odoo import models, fields, api
from odoo.exceptions import ValidationError


state_selection = [
    ('draft', 'Draft'),
    ('clear', 'Clear'),
    ('bounce', 'Bounce'),
    ('cancel', 'Cancelled'),
]


class POSCheque(models.Model):
    _name = 'pos.cheque'
    _description = "POS Cheque"


    donor_id = fields.Many2one('res.partner', string="Donor", compute="_set_details", store=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Acccount", compute="_set_details", store=True)
    
    name = fields.Char('Name')
    
    state = fields.Selection(selection=state_selection, string="State", default='draft')

    order_reference = fields.Char('Order Reference', compute="_set_details", store=True)

    bank_name = fields.Char('Bank Name')

    date = fields.Date('Date')

    bounce_count = fields.Integer('Bounce Count')

    amount = fields.Float('Amount', compute="_set_details", store=True)


    @api.depends('name')
    def _set_details(self):
        for rec in self:
            rec.donor_id = None
            rec.analytic_account_id = None

            rec.amount = 0
            rec.order_reference = f''
            
            pos_order = self.env['pos.order'].search([('pos_cheque_id', '=', rec.id)], limit=1)

            if pos_order:
                rec.donor_id = pos_order.partner_id.id
                rec.analytic_account_id = pos_order.analytic_account_id.id
                
                rec.amount = pos_order.amount_total

                branch_code = pos_order.user_id.employee_id.analytic_account_id.code
                company = pos_order.company_id.name[:3].upper()
                order_date = pos_order.date_order and pos_order.date_order.year or ''
                order_ref = pos_order.name and pos_order.name[-4:] or '0000'

                rec.order_reference = f'{branch_code}-{company}-{order_date}-{order_ref}'

    def action_show_pos_order(self):
        pos_order = self.env['pos.order'].search([('pos_cheque_id', '=', self.id)])

        return {
            'name': 'POS Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            # 'domain': [('pos_cheque_id', '=', self.id)],
            'context': {
                'edit': '0',
                'delete': '0',
            },
            'view_mode': 'form',
            'res_id': pos_order.id,
            'target': 'new',
        }

    def action_clear(self):
        self.state = 'clear'
    
    def action_bounce(self):
        # raise ValidationError('Functionality coming soon')
        if self.bounce_count > 3:
            raise ValidationError('You can not bounce the cheque more then 3 times')

        self.bounce_count += 1
        self.state = 'bounce'
    
    def action_cancel(self):
        self.state = 'cancel'