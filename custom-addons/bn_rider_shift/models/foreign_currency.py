from odoo import models, fields
from odoo.exceptions import UserError


state_selection = [
    ('draft', 'Draft'),
    ('converted', 'Converted'),
    ('reject', 'Reject'),
]


class ForeignCurrency(models.Model):
    _name = 'foreign.currency'
    _description = "Foreign Currency"


    currency_id = fields.Many2one('res.currency', string="Currency")
    
    rider_log = fields.Char('Currency')

    amount = fields.Float('Amount')
    foreign_notes = fields.Float('Foreign Notes')
    exchanged_amount = fields.Float('Exchanged Amount')
    conversion_rate = fields.Float('Conversion Rate', default=1.0)

    rider_id = fields.Many2one('hr.employee', string="Rider")
    lot_id = fields.Many2one('stock.lot', string="Lot")

    state = fields.Selection(selection=state_selection, string="State", default='draft')
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")


    def action_convert_amount(self):
        self.exchanged_amount = self.amount * self.conversion_rate
        self.state = 'converted'

    def action_reject(self):
        self.state = 'reject'

    def action_create_pos_record(self):
        """Create a POS order for the selected foreign currency lines."""
        if 'pos.order' not in self.env:
            raise UserError('POS module is not available in this database.')

        selected_amount = sum(self.mapped('exchanged_amount'))
        if not selected_amount:
            raise UserError('Please select foreign currency lines with a non-zero exchanged amount.')

        current_time = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        pos_name = f"FCB-{current_time.strftime('%Y%m%d%H%M%S')}"
        order_vals = {
            'name': pos_name,
            'amount_total': selected_amount,
            'amount_paid': selected_amount,
            'amount_return': 0.0,
            'state': 'paid',
            'lines': [(0, 0, {
                'name': f'Foreign currency total for {len(self)} line(s)',
                'qty': 1,
                'price_unit': selected_amount,
                'price_subtotal': selected_amount,
                'price_subtotal_incl': selected_amount,
            })],
        }
        pos_order = self.env['pos.order'].create(order_vals)

        return {
            'name': 'POS Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'res_id': pos_order.id,
            'view_mode': 'form',
            'target': 'current',
        }
