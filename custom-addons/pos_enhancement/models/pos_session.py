from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError,AccessError
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'
    
    validation_lines = fields.One2many('order.validate.line', 'pos_session_id',  string='Orders')
    
    def load_pos_data(self):
        loaded_data =super(PosSession, self).load_pos_data()
        _logger.info("loaded_data is called")
        return loaded_data
    
    def _loader_params_res_partner(self):
        return {
            'search_params': {
                'domain': self._get_partners_domain(),
                'fields': [
                    'name', 'street', 'city', 'state_id', 'state', 'donor_type', 'country_id', 'vat', 'lang', 'phone', 'zip', 'mobile', 'email',
                    'barcode', 'write_date', 'property_account_position_id', 'property_product_pricelist', 'parent_name', 'cnic_no', 'donation_type', 
                    'bank_name', 'cheque_number', 'branch_id', 'is_donee', 'company_type', 'gender', 'registration_category'
                ],
                # 'fields': [
                #     'name', 'street', 'city', 'state_id', 'country_id', 'vat', 'lang', 'phone', 'zip', 'mobile', 'email',
                #     'barcode', 'write_date', 'property_account_position_id', 'property_product_pricelist', 'parent_name',
                #     'company_type','gender','cnic_no', 'date_of_birth','age','is_donee', 'state'
                # ],
            },
        }
    
    @api.model
    def _pos_ui_models_to_load(self):
        models_to_load = super(PosSession, self)._pos_ui_models_to_load()
        models_to_load.append('pos.registered.order')
        models_to_load.append('pos.registered.order.line')

        return models_to_load
    
    def _get_pos_ui_pos_registered_order(self,params):
        return self.env['pos.registered.order'].search_read(**params['search_params'])
    
    def _loader_params_pos_registered_order(self):
        return {
            'search_params': {
                'domain': [('state', '=', 'active')],
                'fields': [
                    'name', 'partner_id', 'registrar', 'barcode', 'order_lines',
                ],
            }
        }
        
    # def _loader_params_product_product(self):
    #     return {
    #         'search_params': {
    #             'domain': self.config_id._get_available_product_domain(),
    #             'fields': [
    #                 'display_name', 'lst_price', 'standard_price', 'categ_id', 'pos_categ_ids', 'taxes_id', 'barcode','is_subsidised',
    #                 'default_code', 'to_weight', 'uom_id', 'description_sale', 'description', 'product_tmpl_id', 'tracking',
    #                 'write_date', 'available_in_pos', 'attribute_line_ids', 'active', 'image_128', 'combo_ids',
    #             ],
    #             'order': 'sequence,default_code,name',
    #         },
    #         'context': {'display_default_code': False},
    #     }
        
    def _get_pos_ui_pos_registered_order_line(self,params):
        return self.env['pos.registered.order.line'].search_read(**params['search_params'])
    
    def _loader_params_pos_registered_order_line(self):
        registered_orders = self._context.get('loaded_data')['pos.registered.order']
        order_line_ids = set().union(*[order.get('order_lines') for order in registered_orders])
        return {'search_params': {'fields': ['id', 'product_id', 'qty','price_unit', 'order_id']}, 'ids': order_line_ids}
    
    
    def _get_closed_validation_lines(self):
        return self.validation_lines.filtered(lambda line:  line.payment_ids)
    
    def get_closing_control_data(self):
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("You don't have the access rights to get the point of sale closing control data."))
        self.ensure_one()
        orders = self._get_closed_orders()
        validation_lines = self._get_closed_validation_lines()
        payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later") + validation_lines.payment_ids
        cash_payment_method_ids = self.payment_method_ids.filtered(lambda pm: pm.type == 'cash')
        default_cash_payment_method_id = cash_payment_method_ids[0] if cash_payment_method_ids else None
        total_default_cash_payment_amount = sum(payments.filtered(lambda p: p.payment_method_id == default_cash_payment_method_id).mapped('amount')) if default_cash_payment_method_id else 0
        other_payment_method_ids = self.payment_method_ids - default_cash_payment_method_id if default_cash_payment_method_id else self.payment_method_ids
        cash_in_count = 0
        cash_out_count = 0
        cash_in_out_list = []
        last_session = self.search([('config_id', '=', self.config_id.id), ('id', '!=', self.id)], limit=1)
        for cash_move in self.sudo().statement_line_ids.sorted('create_date'):
            if cash_move.amount > 0:
                cash_in_count += 1
                name = f'Cash in {cash_in_count}'
            else:
                cash_out_count += 1
                name = f'Cash out {cash_out_count}'
            cash_in_out_list.append({
                'name': cash_move.payment_ref if cash_move.payment_ref else name,
                'amount': cash_move.amount
            })

        return {
            'orders_details': {
                'quantity': len(orders) + len(validation_lines),
                'amount': sum(orders.mapped('amount_total')) + sum(validation_lines.mapped('payment_ids').mapped('amount')),
            },
            'opening_notes': self.opening_notes,
            'default_cash_details': {
                'name': default_cash_payment_method_id.name,
                'amount': last_session.cash_register_balance_end_real
                          + total_default_cash_payment_amount
                          + sum(self.sudo().statement_line_ids.mapped('amount')),
                'opening': last_session.cash_register_balance_end_real,
                'payment_amount': total_default_cash_payment_amount,
                'moves': cash_in_out_list,
                'id': default_cash_payment_method_id.id
            } if default_cash_payment_method_id else None,
            'other_payment_methods': [{
                'name': pm.name,
                'amount': sum(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm).mapped('amount')),
                'number': len(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm)),
                'id': pm.id,
                'type': pm.type,
            } for pm in other_payment_method_ids],
            'is_manager': self.user_has_groups("point_of_sale.group_pos_manager"),
            'amount_authorized_diff': self.config_id.amount_authorized_diff if self.config_id.set_maximum_difference else None
        }
