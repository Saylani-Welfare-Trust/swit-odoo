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

    def action_create_donation_box_request(self):
        """Create a Donation Box request for the selected foreign currency lines."""
        donation_box_model = self.env['ir.model'].search([('model', '=', 'donation.box.request')], limit=1)
        if not donation_box_model:
            raise UserError('Donation Box module is not available in this database.')

        invalid_lines = self.filtered(lambda rec: rec.state != 'converted')
        if invalid_lines:
            raise UserError('Only converted foreign currency lines can be used. Please select only converted lines.')

        selected_amount = sum(self.mapped('exchanged_amount'))
        if not selected_amount:
            raise UserError('Please select converted foreign currency lines with a non-zero exchanged amount.')

        current_time = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        donation_box_name = f"FCB-{current_time.strftime('%Y%m%d%H%M%S')}"

        donation_box_request = self.env['donation.box.request'].create({
            'name': donation_box_name,
        })

        return {
            'name': 'Donation Box Request',
            'type': 'ir.actions.act_window',
            'res_model': 'donation.box.request',
            'res_id': donation_box_request.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_pos_record(self):
        """Compatibility wrapper for legacy POS button calls."""
        return self.action_create_donation_box_request()
