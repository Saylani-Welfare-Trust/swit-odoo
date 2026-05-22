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
        
        # Create a dynamic tree view with all disbursement line columns
        tree_arch = """
        <tree>
            <field name="disbursement_category_id" options="{'no_create': True, 'no_edit': True, 'no_open': True}"/>
            <field name="disbursement_application_type_id" options="{'no_create': True, 'no_edit': True, 'no_open': True}"/>
            <field name="product_id" options="{'no_create': True, 'no_edit': True, 'no_open': True}"/>
            <field name="payment_types" />
            <field name="assigned_officer_id" options="{'no_create': True, 'no_edit': True, 'no_open': True}"/>
            <field name="collection_point" />
            <field name="analytic_account_id" options="{'no_create': True, 'no_edit': True, 'no_open': True}"/>
            <field name="collection_date" />
            <field name="marriage_date"/>
            <field name="quantity" />
            <field name="amount" readonly="1" />
            <field name="total_amount" readonly="1" />
            <field name="state" widget="badge" decoration-warning="state == 'draft'" decoration-success="state == 'disbursed'" />
        </tree>
        """
        
        # Get or create the view
        view_obj = self.env['ir.ui.view']
        view_name = f'welfare_line_history_{self.id}_{self.cnic_no.replace("-", "_")}'
        
        existing_view = view_obj.search([('name', '=', view_name)], limit=1)
        if existing_view:
            tree_view = existing_view
        else:
            tree_view = view_obj.create({
                'name': view_name,
                'model': 'welfare.line',
                'arch': tree_arch,
                'type': 'tree',
            })
        
        # Open disbursement lines using the dynamic tree view
        return {
            'type': 'ir.actions.act_window',
            'name': f'Disbursement History - CNIC: {self.cnic_no}',
            'res_model': 'welfare.line',
            'view_type': 'tree',
            'view_id': tree_view.id,
            'views': [(tree_view.id, 'tree')],
            'domain': [('id', 'in', disbursement_lines.ids)],
            'context': {'create': False},
            'target': 'current',
        }