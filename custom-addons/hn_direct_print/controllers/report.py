# addons/hn_direct_print/controllers/report_controller.py
from odoo import http
from odoo.http import request
import base64
from odoo.tools.safe_eval import safe_eval


class ReportController(http.Controller):
    @http.route('/hn_direct_print/base64_report', type='json', auth='user')
    def get_base64_report(self, report_name, docids, context={}):
        """
        Generate the PDF report and return as base64
        """
        context = dict(context or {})

        # Find report action by report_name (external id)
        report_action = request.env['ir.actions.report']._get_report_from_name(report_name)
        if not report_action:
            return {'success': False, 'error': 'Report not found'}

        # Generate PDF
        pdf_content, _ = report_action.with_context(context)._render_qweb_pdf(
            report_name, docids, data=context
        )

        if len(docids) == 1:
            records = request.env[report_action.model].browse(docids)
            filename = safe_eval(
                report_action.print_report_name,
                {
                    'object': records,
                    'objects': records,
                }
            )
        else:
            filename = report_action.name

        # Convert PDF bytes to base64
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

        return {'success': True, 'pdf': pdf_base64, "name": filename + ".pdf"}
