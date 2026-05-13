# In your models/welfare_line_wizard.py
from odoo import models, fields, api

class WelfareLineWizard(models.TransientModel):
    _name = 'welfare.line.wizard'
    _description = 'Welfare Line Details Wizard'

    # Welfare Line fields
    welfare_line_id = fields.Many2one('welfare.line', string='Welfare Line', required=True)
    
    # All fields from welfare.line
    welfare_id = fields.Many2one('welfare.welfare', string='Welfare Record', related='welfare_line_id.welfare_id', readonly=True)
    disbursement_category_id = fields.Many2one('disbursement.category', string='Disbursement Category', related='welfare_line_id.disbursement_category_id', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', related='welfare_line_id.product_id', readonly=True)
    collection_point = fields.Char(string='Collection Point', related='welfare_line_id.collection_point', readonly=True)
    collection_date = fields.Date(string='Collection Date', related='welfare_line_id.collection_date', readonly=True)
    quantity = fields.Float(string='Quantity', related='welfare_line_id.quantity', readonly=True)
    total_amount = fields.Monetary(string='Total Amount', related='welfare_line_id.total_amount', readonly=True)
    state = fields.Selection(related='welfare_line_id.state', string='State', readonly=False)
    
    # Additional information from welfare record
    applicant_name = fields.Char(string='Applicant Name', related='welfare_id.name', readonly=True)
    cnic_no = fields.Char(string='CNIC Number', related='welfare_id.cnic_no', readonly=True)
    father_name = fields.Char(string='Father Name', related='welfare_id.father_name', readonly=True)
    phone = fields.Char(string='Phone', related='welfare_id.phone', readonly=True)
    address = fields.Text(string='Address', related='welfare_id.address', readonly=True)
    
    currency_id = fields.Many2one('res.currency', related='welfare_line_id.currency_id', readonly=True)

    def action_mark_as_collected(self):
        """Mark the welfare line as collected"""
        if self.welfare_line_id:
            self.welfare_line_id.write({'state': 'collected'})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Welfare line marked as collected successfully',
                    'type': 'success',
                    'sticky': False,
                }
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Error',
                'message': 'Failed to mark as collected',
                'type': 'danger',
                'sticky': False,
            }
        }