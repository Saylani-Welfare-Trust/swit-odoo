from odoo import models, fields, api
from odoo.exceptions import ValidationError


class POSSessionSlip(models.Model):
    _name = 'pos.session.slip'
    _description = "POS Session Slip"


    bank_id = fields.Many2one('account.journal', string="Bank")
    session_id = fields.Many2one('pos.session', string="Session")
    pos_payment_method_id = fields.Many2one('pos.payment.method', string="Payment Method")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    type = fields.Char('Type')
    slip_no = fields.Char('Deposit Slip No.')

    amount = fields.Monetary('Amount', currency_field='currency_id')


    @api.model
    def create_session_slip(self, session_id, data):
        if not data or not session_id:
            return {
                "status": "error"
            }

        # raise ValidationError(str(session_id) + "----" + str(data))
        # raise ValidationError(str(session_id) + "----" + str(data) + "----" + str(pos_payment_method.name))

        record = self.create({
            'bank_id': data['bank_id'],
            'pos_payment_method_id': data['payment_method_id'],
            'type': self.env.company.unrestricted_category if data['type'] == 'unrestricted' else self.env.company.restricted_category if data['type'] == 'restricted' else "Uncategorized",
            'slip_no': data['ref'],
            'amount': data['amount'],
            'session_id': session_id
        })

        return {
            "status": "success",
            "id": record.id
        }
    
    @api.model
    def delete_session_slip(self, record_id):
        if not record_id:
            return {
                "status": 'error'
            }
        
        if self.browse(record_id).unlink():
            return {
                "status": 'success'
            }
    
    @api.model
    def delete_session_slips_for_session(self, session_id):
        if not session_id:
            return {
                "status": 'error'
            }
        
        if self.search([('session_id', '=', session_id)]).unlink():
            return {
                "status": 'success'
            }