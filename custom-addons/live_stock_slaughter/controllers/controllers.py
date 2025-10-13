from odoo import http
from odoo.http import request

class LiveStockSlaughterController(http.Controller):

    @http.route('/live_slaughter/<int:rec_id>/<string:token>', type='http', auth='user')
    def process_slaughter(self, rec_id, token, **kwargs):
        record = request.env['live_stock_slaughter.live_stock_slaughter'].sudo().browse(rec_id)

        if not record.exists() or record.access_token != token:
            return request.not_found()

        # Call your methods safely
        try:
            if hasattr(record, 'action_confirm'):
                record.action_confirm()
            if hasattr(record, 'action_cutting'):
                record.action_cutting()
        except Exception as e:
            return f"Error processing record: {str(e)}"

        # Redirect back to normal backend form view (your current working link)
        return request.redirect(
            f"/web#id={record.id}&model=live_stock_slaughter.live_stock_slaughter&view_type=form"
        )
