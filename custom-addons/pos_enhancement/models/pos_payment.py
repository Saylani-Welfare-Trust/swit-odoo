from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.payment'
    
    validation_line_id = fields.Many2one('order.validate.line', string='Validation Line')
    pos_order_id = fields.Many2one('pos.order', string='Order', required=False, index=True)
    validation_session_id = fields.Many2one('pos.session', string='Session', related='validation_line_id.pos_session_id', store=True)
    company_id = fields.Many2one('res.company', string='Company',related=False,compute="_compute_company",store=True, readonly=True, index=True)
    
    @api.depends('pos_order_id', 'validation_line_id')
    def _compute_session(self):
        for rec in self:
            if rec.pos_order_id:
                rec.session_id = rec.pos_order_id.session_id
            else:
                rec.session_id = rec.validation_line_id.pos_session_id
                
    @api.constrains('payment_method_id')
    def _check_payment_method_id(self):
        for payment in self:
            # raise UserError(str(payment.session_id))
            # if payment.payment_method_id not in payment.session_id.config_id.payment_method_ids:
            #     raise UserError(_('The payment method selected is not allowed in the config of the POS session.'))
            if payment.pos_order_id :
                if payment.payment_method_id not in payment.session_id.config_id.payment_method_ids:
                    raise ValidationError(_('The payment method selected is not allowed in the config of the POS session.'))
            else:
                if payment.payment_method_id not in payment.validation_line_id.pos_session_id.config_id.payment_method_ids:
                    raise ValidationError(_('The payment method selected is not allowed in the config of the POS session.'))
    
    _sql_constraints = [
        ('check_pos_or_register_order', 
         'CHECK ((pos_order_id IS NOT NULL AND validation_line_id IS NULL) OR (pos_order_id IS NULL AND validation_line_id IS NOT NULL))', 
         'Either POS Order or Register Order must be provided, but not both.')
    ]
    
    @api.depends('pos_order_id', 'validation_line_id')
    def _compute_company(self):
        for rec in self:
            # raise UserError(str(rec.pos_order_id))
            if rec.pos_order_id:
                rec.company_id = rec.pos_order_id.company_id
            else:
                # raise UserError(str(rec.validation_line_id))
                rec.company_id = rec.validation_line_id.pos_session_id.company_id