import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class POSCheque(models.Model):
    _inherit = 'pos.cheque'

    source_model = fields.Selection(selection_add=[('medical_equipment', 'Medical Equipment')])
    medical_security_deposit_id = fields.Many2one('medical.security.deposit', string="Security Deposit")

    def _find_security_deposit(self):
        """Security deposit of the medical equipment request the cheque paid."""
        self.ensure_one()
        if not self.source_record_id:
            return self.env['medical.security.deposit']
        equipment = self.env['medical.equipment'].sudo().browse(self.source_record_id).exists()
        if not equipment:
            return self.env['medical.security.deposit']
        return equipment.sd_slip_id or self.env['medical.security.deposit'].sudo().search(
            [('medical_equipment_id', '=', equipment.id)], limit=1)

    def link_security_deposit(self):
        """Link the security deposit to this cheque if not already linked"""
        self.ensure_one()
        if self.source_model != 'medical_equipment':
            return False
        if not self.medical_security_deposit_id:
            sd_slip = self._find_security_deposit()
            if not sd_slip:
                return False
            self.sudo().medical_security_deposit_id = sd_slip
        return True

    def _ensure_security_deposit_link(self):
        self.ensure_one()
        if self.source_model == 'medical_equipment':
            self.link_security_deposit()
            return self.medical_security_deposit_id
        return self.env['medical.security.deposit']

    def _clear_medical_equipment(self):
        self.ensure_one()
        security_deposit = self._ensure_security_deposit_link()
        if security_deposit and security_deposit.medical_equipment_id:
            security_deposit.medical_equipment_id._receive_security_deposit('paid')
        elif security_deposit:
            security_deposit.write({'state': 'paid'})
        else:
            _logger.warning("No security deposit found for cheque %s", self.name)

    def _bounce_medical_equipment(self):
        self.ensure_one()
        security_deposit = self._ensure_security_deposit_link()
        if security_deposit and security_deposit.medical_equipment_id:
            security_deposit.medical_equipment_id._bounce_security_deposit(security_deposit)
        elif security_deposit:
            security_deposit.write({'state': 'bounced'})
        else:
            _logger.warning("No security deposit found for cheque %s", self.name)

    def action_view_security_deposit(self):
        """View the linked security deposit"""
        self.ensure_one()
        if self.medical_security_deposit_id:
            return {
                'name': 'Security Deposit',
                'type': 'ir.actions.act_window',
                'res_model': 'medical.security.deposit',
                'view_mode': 'form',
                'res_id': self.medical_security_deposit_id.id,
                'target': 'new',
            }

    def action_clear(self):
        res = super().action_clear()
        for rec in self.filtered(lambda c: c.source_model == 'medical_equipment'):
            rec.sudo()._clear_medical_equipment()
        return res

    def action_bounce(self):
        res = super().action_bounce()
        for rec in self.filtered(lambda c: c.source_model == 'medical_equipment'):
            rec.sudo()._bounce_medical_equipment()
        return res

    def action_cancel(self):
        if self.filtered(lambda c: c.source_model == 'medical_equipment'):
            raise UserError(_('Cannot cancel cheque for medical equipment. Please contact support.'))
        return super().action_cancel()


class POSOrder(models.Model):
    _inherit = 'pos.order'

    def _prepare_pos_cheque_vals(self, ui_order, vals):
        vals = super()._prepare_pos_cheque_vals(ui_order, vals)
        extra_data = ui_order.get('extra_data') or {}
        me_data = extra_data.get('medical_equipment')
        if me_data and not extra_data.get('welfare'):
            equipment_id = me_data.get('medical_equipment_id')
            vals['source_model'] = 'medical_equipment'
            vals['source_record_id'] = equipment_id
            # the payload carries security_deposit_id when the deposit exists;
            # else medical.security.deposit links the cheque once it is created
            sd_id = me_data.get('security_deposit_id')
            if not sd_id and equipment_id:
                equipment = self.env['medical.equipment'].sudo().browse(equipment_id).exists()
                sd_id = (equipment.sd_slip_id or self.env['medical.security.deposit'].sudo().search(
                    [('medical_equipment_id', '=', equipment_id)], limit=1)).id if equipment else False
            if sd_id:
                vals['medical_security_deposit_id'] = sd_id
        return vals
