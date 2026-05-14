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
        
        # Collect all disbursement lines from these welfare records
        disbursement_lines = self.env['welfare.line']
        for welfare in welfare_records:
            if welfare.welfare_line_ids:
                disbursement_lines |= welfare.welfare_line_ids
        
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
        
        # Open disbursement lines in a list view
        return {
            'type': 'ir.actions.act_window',
            'name': f'Disbursement History - CNIC: {self.cnic_no}',
            'res_model': 'welfare.line',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', disbursement_lines.ids)],
            'target': 'current',
        }