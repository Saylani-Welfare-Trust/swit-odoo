from odoo import fields, api, models,_, exceptions
from collections import namedtuple
import logging

_logger = logging.getLogger(__name__)


class MfdLoanRequest(models.Model):
    _inherit = 'mfd.loan.request'

    @api.model
    def check_loan_ids(self,data):
        if not data:
            return {
                "status": "error",
                "body": "Please enter CNIC number",
            }

        loan_ids = self.sudo().search([('name', '=', data)])
        if not loan_ids:
            return {
                "status": "error",
                "body": "Record not found",
            }

        bank_ids = self.env['mfd.bank'].search([('is_active', '=', True)])

        return {
            "status": "success",
            'loan_ids': [{'id': l.id, 'name': l.name, 'customer_name': l.customer_id.name, 'asset_type': l.asset_type,
                          'product': l.product_id.name, 'currency_id': l.currency_id.id, 'currency_symbol': l.currency_id.symbol}
                         for l in loan_ids],
            'bank_ids': [{'id': bank.id, 'name': bank.name} for bank in bank_ids]
        }

# class MfdInstallmentReceipt(models.Model):
#     _inherit = 'mfd.installment.receipt'


#     @api.model
#     def register_pos_mfd_payment(self, data):
#         products_data = []

        
#         # Add delivery charges if applicable
#         donation_recipet = data['amount']
        
#         if data['doctype'] == 'sec_dep':
#             security_amount = data['doctype']

        
#         if donation_recipet and float(donation_recipet) > 0:
#             service_product = self.env['product.product'].search([
#                 ('name', '=', 'Donation Recipet'),
#                 ('type', '=', 'service'),
#                 ('available_in_pos', '=', True)
#             ], limit=1)
            
#             if service_product:
#                 products_data.append({
#                     'product_id': service_product.id,
#                     'name': service_product.name,
#                     'quantity': 1,
#                     'price': float(donation_recipet),
#                     'default_code': service_product.default_code ,
#                     'category': service_product.categ_id.name if service_product.categ_id else 'Services',
            
#                 })


#             if security_amount :
#                  _logger.info("Security Amount Processed: %s", security_amount)
                
#                  payment = self.env['mfd.installment.receipt'].create({

#                 'doc_type': data['doc_type'],
#                 'payment_type': data['payment_type'],
#                 'amount': data['amount'],
#                 'currency_id': data['currency_id'],
#                 'loan_id': data['loan_id']
#             })
            
#             _logger.info("Payment Record Created: %s", payment)
                 
                 
#             payment.action_paid()
        

#         _logger.info("Final Products Data: %s", products_data,'reprt_id',payment.id)
        
#         return {
#             # "report_id": payment.id,
#             # 'security_amount': security_amount,
#             'partner_id': data['partner_id'],
#             'products': products_data,
#             'success': True
#         }


         

class MfdInstallmentReceipt(models.Model):
    _inherit = 'mfd.installment.receipt'

    @api.model
    def register_pos_mfd_payment(self, data):
        products_data = []
        security_amount = False
        
        # Add delivery charges if applicable
        donation_recipet = data['amount']
        
        # FIXED: Changed 'doctype' to 'doc_type'
        if data['doc_type'] == 'sec_dep':
            security_amount = data['doc_type']

        if donation_recipet and float(donation_recipet) > 0:
            service_product = self.env['product.product'].search([
                ('name', '=', 'Donation Recipet'),
                ('type', '=', 'service'),
                ('available_in_pos', '=', True)
            ], limit=1)
            
            if service_product:
                products_data.append({
                    'product_id': service_product.id,
                    'name': service_product.name,
                    'quantity': 1,
                    'price': float(donation_recipet),
                    'default_code': service_product.default_code,
                    'category': service_product.categ_id.name if service_product.categ_id else 'Services',
                })

        # FIXED: Check if security_amount is truthy (not just exists)
            if security_amount:
                _logger.info("Security Amount Processed: %s", security_amount)
                
                payment = self.env['mfd.installment.receipt'].create({
                    'doc_type': data['doc_type'],
                    'payment_type': data['payment_type'],
                    'amount': data['amount'],
                    'currency_id': data['currency_id'],
                    'loan_id': data['loan_id']
                })
                
                _logger.info("Payment Record Created: %s", payment)
                payment.action_paid()

            _logger.info("Final Products Data: %s", products_data)

        partner_id = self.env['res.partner'].search([('name', '=', data['partner_id'])], limit=1)
        
        # raise exceptions.ValidationError(partner_id)

        return {
            'partner_id': partner_id.id,
            'products': products_data,
            'success': True,
            'security_amount': security_amount if security_amount else False,
            'report_id': payment.id if security_amount else False  # Only include if payment was created
        }














        # print(data)
        # if not data['amount'] or float(data['amount']) <= 0:
        #     return {
        #         "status": "error",
        #         "body": "Please enter amount",
        #     }

        # if data['payment_type'] == 'cheque':
        #     if not data['bank_id']:
        #         return {
        #             "status": "error",
        #             "body": "Please select bank",
        #         }
        #     if not data['cheque_number']:
        #         return {
        #             "status": "error",
        #             "body": "Please enter cheque number",
        #         }
        #     if not data['cheque_date']:
        #         return {
        #             "status": "error",
        #             "body": "Please enter cheque date",
        #         }
        #     payment = self.env['mfd.installment.receipt'].create({
        #             'doc_type': data['doc_type'],
        #             'payment_type': data['payment_type'],
        #             'amount': data['amount'],
        #             'currency_id': data['currency_id'],
        #             'loan_id': data['loan_id'],
        #             'mfd_bank_id': data['bank_id'],
        #             'cheque_number': data['cheque_number'],
        #             'cheque_date': data['cheque_date']
        #     })
        #     payment.action_pending()

        # else:
        #     payment = self.env['mfd.installment.receipt'].create({
        #         'doc_type': data['doc_type'],
        #         'payment_type': data['payment_type'],
        #         'amount': data['amount'],
        #         'currency_id': data['currency_id'],
        #         'loan_id': data['loan_id']
        #     })
        #     payment.action_paid()

        # session_id = self.env['pos.session'].search([('id', '=', data['pos_session_id'])])

        # if not session_id.microfinance_order_id:
        #     microfinance_order_id = self.env['pos.order'].create(
        #         {
        #             'session_id': session_id.id,
        #             'amount_tax': 0,
        #             'amount_total': 0,
        #             'amount_paid': 0,
        #             'amount_return': 0,
        #             'is_microfinance_order': True

        #         }
        #     )
        #     microfinance_order_id.action_pos_order_paid()
        #     session_id.microfinance_order_id = microfinance_order_id

        # session_id.microfinance_order_id.write({
        #     'amount_total': session_id.microfinance_order_id.amount_total + float(data['amount']),
        #     'amount_paid': session_id.microfinance_order_id.amount_paid + float(data['amount']),
        # })
        # payment_method_id = None
        # if data['payment_type'] == 'cheque':
        #     payment_method_id = self.env['pos.payment.method'].search([('is_bank', '=', True)], limit=1)
        # else:
        #     payment_method_id = self.env['pos.payment.method'].search([('name', '=', 'Cash')], limit=1)
        # print('payment_method_id', payment_method_id)
        # session_id.create_microfinance_payment(session_id.id, session_id.microfinance_order_id.id, payment_method_id.id, data['amount'])


        # return {
        #     "report_id": payment.id,
        #     "status": "success",
        # }

