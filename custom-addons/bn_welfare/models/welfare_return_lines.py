# models/welfare_consolidated.py

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class WelfareConsolidatedLine(models.Model):
    _name = 'welfare.consolidated.line'
    _description = 'Consolidated Welfare Lines'
    _rec_name = 'display_name'
    _order = 'collection_date desc'
    
    # All fields from both models
    employee_id = fields.Many2one('hr.employee', string='Employee')
    disbursement_category_id = fields.Many2one('disbursement.category', string='Category')
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', string='Application Type')
    product_id = fields.Many2one('product.product', string='Product')
    payment_type = fields.Selection([
        ('self', 'Self'),
        ('officer', 'Officer'),
    ], string='Payment Type')
    assigned_officer_id = fields.Many2one('hr.employee', string='Assigned Officer')
    collection_point = fields.Selection([
        ('bank', 'Bank'),
        ('cash', 'Cash'),
    ], string='Collection Point')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    collection_date = fields.Date(string='Collection Date')
    marriage_date = fields.Date(string='Marriage Date')
    quantity = fields.Float(string='Quantity')
    amount = fields.Float(string='Amount')
    total_amount = fields.Float(string='Total Amount')
    advance_donation_amount = fields.Float(string='Advance Donation Amount')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('disbursed', 'Disbursed'),
        ('return', 'Return'),
        ('recurring', 'Recurring'),
    ], string='State')
    
    # Recurring specific fields
    is_recurring = fields.Boolean(string='Is Recurring')
    recurring_duration = fields.Integer(string='Recurring Duration')
    
    # Tracking fields
    source_model = fields.Char(string='Source Model')
    source_id = fields.Integer(string='Source ID')
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=False)
    
    @api.depends('is_recurring', 'employee_id')
    def _compute_display_name(self):
        for record in self:
            prefix = "Recurring" if record.is_recurring else "Regular"
            name = record.employee_id.name if record.employee_id else "Unknown"
            record.display_name = f"{prefix} - {name}"
    
    @api.model
    def _get_source_records(self, domain=None):
        """Get records from both source models"""
        records = []
        
        # Get regular welfare lines
        welfare_domain = domain or []
        welfare_lines = self.env['welfare.line'].search(welfare_domain)
        
        # Get recurring welfare lines
        recurring_lines = self.env['welfare.recurring.line'].search(welfare_domain)
        
        # Convert to consolidated records
        for line in welfare_lines:
            records.append({
                'source_model': 'welfare.line',
                'source_id': line.id,
                'is_recurring': False,
                'employee_id': line.employee_id.id,
                'disbursement_category_id': line.disbursement_category_id.id,
                'disbursement_application_type_id': line.disbursement_application_type_id.id,
                'product_id': line.product_id.id,
                'payment_type': line.payment_type,
                'assigned_officer_id': line.assigned_officer_id.id,
                'collection_point': line.collection_point,
                'analytic_account_id': line.analytic_account_id.id,
                'collection_date': line.collection_date,
                'marriage_date': line.marriage_date,
                'quantity': line.quantity,
                'amount': line.amount,
                'total_amount': line.total_amount,
                'advance_donation_amount': line.advance_donation_amount,
                'state': line.state,
                'recurring_duration': 0,
            })
        
        for line in recurring_lines:
            records.append({
                'source_model': 'welfare.recurring.line',
                'source_id': line.id,
                'is_recurring': True,
                'employee_id': line.employee_id.id,
                'disbursement_category_id': line.disbursement_category_id.id,
                'disbursement_application_type_id': line.disbursement_application_type_id.id,
                'product_id': line.product_id.id,
                'payment_type': line.payment_type,
                'assigned_officer_id': line.assigned_officer_id.id,
                'collection_point': line.collection_point,
                'analytic_account_id': line.analytic_account_id.id,
                'collection_date': line.collection_date,
                'marriage_date': None,  # Recurring might not have this
                'quantity': line.quantity,
                'amount': line.amount,
                'total_amount': line.total_amount,
                'advance_donation_amount': 0.0,
                'state': line.state,
                'recurring_duration': line.recurring_duration,
            })
        
        return records
    
    @api.model
    def search(self, domain=None, offset=0, limit=None, order=None, count=False):
        """Override search to combine results from both models"""
        if domain is None:
            domain = []
        
        # Get all records from both models
        all_records = self._get_source_records(domain)
        
        # Apply sorting
        if order:
            order_by = order.split()[0] if order else 'collection_date'
            reverse = 'desc' in order.lower()
            all_records.sort(key=lambda x: x.get(order_by, ''), reverse=reverse)
        else:
            all_records.sort(key=lambda x: x.get('collection_date') or '', reverse=True)
        
        # Apply pagination
        if limit:
            all_records = all_records[offset:offset + limit]
        else:
            all_records = all_records[offset:]
        
        if count:
            return len(all_records)
        
        # Create and return the consolidated records
        result = self
        for rec_data in all_records:
            # Create a new record in the consolidated model
            new_record = self.new(rec_data)
            result |= new_record
        
        return result
    
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=None, lazy=True):
        """Override read_group for grouping support"""
        # Get all records
        all_records = self._get_source_records(domain)
        
        # Simple grouping implementation
        if groupby:
            group_field = groupby[0]
            grouped_data = {}
            
            for rec in all_records:
                key = rec.get(group_field)
                if key not in grouped_data:
                    grouped_data[key] = {
                        '__domain': [(group_field, '=', key)],
                        '__count': 0,
                        'id': key,
                    }
                    # Initialize fields with sum
                    for field in fields:
                        if field == '__count':
                            continue
                        if field.endswith(':sum'):
                            field_name = field.split(':')[0]
                            grouped_data[key][field] = 0.0
                        else:
                            grouped_data[key][field] = rec.get(field)
                
                grouped_data[key]['__count'] += 1
                for field in fields:
                    if field.endswith(':sum'):
                        field_name = field.split(':')[0]
                        grouped_data[key][field] += rec.get(field_name, 0.0)
            
            return list(grouped_data.values())
        
        return super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)
    
    def action_open_source_record(self):
        """Open the source record (regular or recurring)"""
        self.ensure_one()
        if self.source_model == 'welfare.line':
            action = self.env.ref('your_module.action_welfare_line').read()[0]
            action['res_id'] = self.source_id
            action['view_mode'] = 'form'
            return action
        elif self.source_model == 'welfare.recurring.line':
            action = self.env.ref('your_module.action_welfare_recurring_line').read()[0]
            action['res_id'] = self.source_id
            action['view_mode'] = 'form'
            return action
        return None