from odoo import api, fields, models


class ReportWelfarePaymentVoucher(models.AbstractModel):
    _name = 'report.bn_welfare.report_welfare_payment_voucher'
    _description = 'Welfare Payment Voucher'

    @api.model
    def _get_report_values(self, docids, data=None):
        lines = self.env['welfare.line'].browse(docids)
        # the Print menu too: only lines of an approved application
        lines._check_payment_voucher()
        lines = lines.sorted(lambda l: (l.welfare_id.id, l.id))
        # Voucher #: <case number>-<line number on the application>
        refs = {}
        for welfare in lines.welfare_id:
            for number, line in enumerate(welfare.welfare_line_ids.sorted('id'), start=1):
                refs[line.id] = '%s-%s' % (welfare.name, number)
        return {
            'doc_ids': lines.ids,
            'doc_model': 'welfare.line',
            'docs': lines,
            'voucher_refs': refs,
            'printed_by': self.env.user.name,
            'printed_on': fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d.%m.%Y %I:%M %p'),
        }
