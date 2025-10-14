from odoo import fields, models, api

class OrderValidateLine(models.Model):
    _name="order.validate.line"

    order_id=fields.Many2one('pos.registered.order',string="Order")
    print_date=fields.Datetime(string="Print Date")
    validation_date=fields.Datetime(string="Validation Date")
    reference_no=fields.Char(string="Reference No")
    validated_by=fields.Many2one('res.users',string="Validated By")
    pos_session_id=fields.Many2one('pos.session',string="POS Session")
    payment_ids = fields.One2many('pos.payment', 'validation_line_id', string='Payments', readonly=True)
    journal_entry = fields.Many2one('account.move',string="Journal Entry")
    
    
    
    