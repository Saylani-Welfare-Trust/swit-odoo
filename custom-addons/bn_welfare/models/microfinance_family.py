from odoo import models, fields, api


class MicrofinanceFamily(models.Model):
    _inherit = 'microfinance.family'


    welfare_id = fields.Many2one('welfare', string="Welfare")

    def action_view_disbursement_history(self):
        """View all welfare disbursement lines for donee matching this family member's CNIC"""
        self.ensure_one()
        
        if not self.cnic_no:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No CNIC Found',
                    'message': 'Please enter a CNIC number to view history.',
                    'type': 'warning',
                }
            }
        
        # Find welfare records (donees) with matching CNIC
        welfare_records = self.env['welfare'].search([
            ('cnic_no', '=', self.cnic_no)
        ])
        
        if not welfare_records:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Donee Found',
                    'message': f'No donee found with CNIC: {self.cnic_no}',
                    'type': 'info',
                }
            }
        
        # Get all disbursement lines from these welfare records
        disbursement_lines = self.env['welfare.line'].search([
            ('welfare_id', 'in', welfare_records.ids)
        ])
        
        if not disbursement_lines:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Disbursement Lines Found',
                    'message': f'No disbursement lines found for donee with CNIC: {self.cnic_no}',
                    'type': 'info',
                }
            }
        
        # Open disbursement lines in a list view with all available fields
        return {
            'type': 'ir.actions.act_window',
            'name': f'Disbursement History - CNIC: {self.cnic_no}',
            'res_model': 'welfare.line',
            'view_mode': 'tree,form',
            'view_id': self.env.ref('bn_welfare.view_welfare_line_tree').id if self.env.ref('bn_welfare.view_welfare_line_tree', raise_if_not_found=False) else False,
            'domain': [('id', 'in', disbursement_lines.ids)],
            'context': {
                'create': False,  # Disable creating new lines from history view
                'edit': False,    # Disable editing from history view (optional)
            },
            'target': 'current',
        }