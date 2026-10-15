from odoo import http
from odoo.http import request

class TreasuryDashboardController(http.Controller):

    def _get_custom_model_stats(self, model_name, amount_field='amount', state_field='state'):
        """Helper to safely fetch stats for custom models if they exist"""
        if model_name not in request.env:
            return {'count': 0, 'total_amount': 0.0, 'states': {}}
        
        try:
            records = request.env[model_name].search([])
            total_amount = sum(records.mapped(amount_field))
            
            states = {}
            if state_field:
                groups = request.env[model_name].read_group([], ['id:count'], [state_field], lazy=False)
                for g in groups:
                    state_val = g.get(state_field)
                    if state_val:
                        states[state_val] = g['id_count']
                        
            return {
                'count': len(records), 
                'total_amount': total_amount, 
                'states': states
            }
        except Exception:
            return {'count': 0, 'total_amount': 0.0, 'states': {}}

    @http.route('/treasury/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        # Fetch stats for the 3 custom models based on your screenshots
        # Note: journal.transfer uses 'status' instead of 'state' based on your screenshot
        return {
            'cheques': self._get_custom_model_stats('pos.cheque', 'amount', 'state'),
            'deposits': self._get_custom_model_stats('direct.deposit', 'amount', 'state'),
            'transfers': self._get_custom_model_stats('journal.transfer', 'amount', 'status'),
        }