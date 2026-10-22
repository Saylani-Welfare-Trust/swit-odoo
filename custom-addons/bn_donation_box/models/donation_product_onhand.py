from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DonationProductOnhand(models.Model):
    _name = 'donation.product.onhand'
    _description = 'Donation Product On-hand Quantity'
    _order = 'location_name, product_name'
    

    product_id = fields.Integer(string='Product ID', readonly=True)
    product_name = fields.Char(string='Product Name', readonly=True)
    location_id = fields.Integer(string='Location ID', readonly=True)
    location_name = fields.Char(string='Location Name', readonly=True)
    on_hand_qty = fields.Float(string='On-Hand Quantity', readonly=True)
    analytic_account_id = fields.Integer(string='Analytic Account ID', readonly=True)
    
    def _get_user_analytic_account(self):
        """Get current user's analytic account"""
        user_employee = self.env.user.employee_id
        if user_employee and user_employee.analytic_account_id:
            return user_employee.analytic_account_id
        return None

    @api.model
    def _get_onhand_data(self):
        """Get on-hand quantity data for donation products"""
        # Get the current user's employee analytic account
        user_analytic = self._get_user_analytic_account()
        user_analytic_id = user_analytic.id if user_analytic else None
        
        # Get all donation products
        donation_products = self.env['product.template'].search([
            ('is_donation_box', '=', True)
        ])
        
        # Get all internal stock locations
        locations = self.env['stock.location'].search([('usage', '=', 'internal')])
        
        # Filter by user's analytic account in Python (more robust)
        if user_analytic_id:
            locations = locations.filtered(lambda loc: loc.analytic_account_id and loc.analytic_account_id.id == user_analytic_id)
        
        records = []
        record_id = 1
        
        # Build records for each product-location combination
        for product_tmpl in donation_products:
            for location in locations:
                # Get on-hand quantity for each product variant
                product_variants = product_tmpl.product_variant_ids if product_tmpl.product_variant_ids else [
                    self.env['product.product'].search([('product_tmpl_id', '=', product_tmpl.id)], limit=1)
                ]
                
                for product in product_variants:
                    if not product:
                        continue
                        
                    stock_quants = self.env['stock.quant'].search([
                        ('product_id', '=', product.id),
                        ('location_id', '=', location.id),
                    ])
                    on_hand_qty = sum(stock_quants.mapped('available_quantity'))
                    
                    records.append({
                        'id': record_id,
                        'product_id': product.id,
                        'product_name': product_tmpl.name,
                        'location_id': location.id,
                        'location_name': location.name,
                        'on_hand_qty': on_hand_qty,
                        'analytic_account_id': location.analytic_account_id.id if location.analytic_account_id else None,
                    })
                    record_id += 1
        
        return records

    @api.model
    def web_search_read(self, domain=None, specification=None, offset=0, limit=None, order=None, **kwargs):
        """Override web_search_read to return dynamic data for web interface"""
        data = self._get_onhand_data()
        
        # Apply domain filters
        if domain:
            for arg in domain:
                if isinstance(arg, tuple) and len(arg) == 3:
                    field, operator, value = arg
                    data = [rec for rec in data if self._apply_filter(rec, field, operator, value)]
        
        # Get total count
        total_count = len(data)
        
        # Apply offset and limit
        if offset:
            data = data[offset:]
        if limit:
            data = data[:limit]
        
        # Build the result with proper field selection
        result = {
            'length': total_count,
            'records': data
        }
        
        return result

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """Override search to return virtual record IDs"""
        data = self._get_onhand_data()
        
        # Apply domain filters
        for arg in args:
            if isinstance(arg, tuple) and len(arg) == 3:
                field, operator, value = arg
                data = [rec for rec in data if self._apply_filter(rec, field, operator, value)]
        
        # Extract IDs
        record_ids = [rec['id'] for rec in data]
        
        # Apply offset and limit
        if offset:
            record_ids = record_ids[offset:]
        if limit:
            record_ids = record_ids[:limit]
        
        if count:
            return len(record_ids)
        
        # Create temporary records from the data
        self._cache = {rec['id']: rec for rec in self._get_onhand_data()}
        records = self.env[self._name]
        for rec_data in data:
            records |= self.browse(rec_data['id'])
        
        return records

    @api.model
    def read(self, ids, fields=None, load='_classic_read'):
        """Override read to return dynamic data"""
        data = self._get_onhand_data()
        cache = {rec['id']: rec for rec in data}
        
        result = []
        for record_id in ids:
            if record_id in cache:
                rec = cache[record_id].copy()
                if fields:
                    rec = {k: v for k, v in rec.items() if k in fields or k == 'id'}
                result.append(rec)
        
        return result

    @staticmethod
    def _apply_filter(record, field, operator, value):
        """Apply filter logic for search domains"""
        record_value = record.get(field)
        
        if operator == '=':
            return record_value == value
        elif operator == '!=':
            return record_value != value
        elif operator == '<':
            return record_value is not None and record_value < value
        elif operator == '>':
            return record_value is not None and record_value > value
        elif operator == '<=':
            return record_value is not None and record_value <= value
        elif operator == '>=':
            return record_value is not None and record_value >= value
        elif operator == 'in':
            return record_value in value if record_value is not None else False
        elif operator == 'not in':
            return record_value not in value if record_value is not None else True
        elif operator == 'ilike':
            return str(record_value).lower().find(str(value).lower()) != -1 if record_value else False
        
        return True
