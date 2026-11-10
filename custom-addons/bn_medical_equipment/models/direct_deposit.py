from odoo import _, fields, models
from odoo.exceptions import UserError


class DirectDeposit(models.Model):
    _inherit = 'direct.deposit'

    source_model = fields.Selection(selection_add=[('medical_equipment', 'Medical Equipment')],
                                    ondelete={'medical_equipment': 'set null'})
    medical_security_deposit_id = fields.Many2one('medical.security.deposit', string="Security Deposit")

    def _prepare_dd_source_vals(self, data):
        if data.get('source_request_type') != 'Medical Equipment' or not data.get('source_request_no'):
            return super()._prepare_dd_source_vals(data)

        equipment = self.env['medical.equipment'].sudo().search([('name', '=', data['source_request_no'])], limit=1)
        if not equipment:
            raise UserError(_('Medical Equipment request %s was not found.') % data['source_request_no'])
        return {
            'source_model': 'medical_equipment',
            'source_record_id': equipment.id,
            'medical_security_deposit_id': equipment._get_security_deposit().id,
        }

    def _clear_source(self):
        if self.source_model != 'medical_equipment':
            return super()._clear_source()
        equipment = self.env['medical.equipment'].sudo().browse(self.source_record_id).exists()
        if not equipment:
            return False
        deposit = equipment._receive_security_deposit('paid', {
            'payment_method': 'cheque' if self.bank_id else 'cash',
            'bank_name': self.bank_id.name or False,
        })
        self.medical_security_deposit_id = deposit
        return True
