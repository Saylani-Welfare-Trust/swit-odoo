from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


def html_table(headers, rows, empty):
    if not rows:
        return Markup('<p>%s</p>') % empty
    cell = 'border: 1px solid #ddd; padding: 8px;'
    head = Markup('').join(Markup('<th style="%s">%s</th>') % (cell, h) for h in headers)
    body = Markup('').join(
        Markup('<tr>%s</tr>') % Markup('').join(Markup('<td style="%s">%s</td>') % (cell, v if v not in (False, None) else '') for v in row)
        for row in rows
    )
    return Markup('<table class="table" style="width:100%%; border-collapse: collapse;">'
                  '<thead><tr style="background-color: #f0f0f0;">%s</tr></thead><tbody>%s</tbody></table>') % (head, body)


class SadqaJariyaReviewWizard(models.TransientModel):
    """Committee / HOD review: the whole application on one page, then approve"""
    _name = 'sadqa.jariya.review.wizard'
    _description = 'Sadqa e Jariya Review'

    application_id = fields.Many2one('sadqa.jariya', string='Application', required=True, readonly=True)
    state = fields.Selection(related='application_id.state')
    donee_id = fields.Many2one(related='application_id.donee_id')
    institution_category = fields.Selection(related='application_id.institution_category')
    subcategory = fields.Char(related='application_id.subcategory')
    institute_name = fields.Char(related='application_id.institute_name')
    address = fields.Char(related='application_id.address')
    order_type = fields.Selection(related='application_id.order_type')
    employee_id = fields.Many2one(related='application_id.employee_id')
    account_title = fields.Char(related='application_id.account_title')
    account_number = fields.Char(related='application_id.account_number')

    committee_remarks = fields.Text('Committee Remarks')
    hod_remarks = fields.Text('HOD Remarks')

    lines_html = fields.Html('Disbursement Items', compute='_compute_html', sanitize=False)
    inquiry_reports_html = fields.Html('Inquiry Reports', compute='_compute_html', sanitize=False)
    committee_members_html = fields.Html('Committee Members', compute='_compute_html', sanitize=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        application = self.env['sadqa.jariya'].browse(res.get('application_id'))
        res['committee_remarks'] = application.committee_remarks
        res['hod_remarks'] = application.hod_remarks
        return res

    @api.depends('application_id')
    def _compute_html(self):
        for rec in self:
            app = rec.application_id
            rec.lines_html = html_table(
                [_('Product'), _('Category'), _('Quantity'), _('Total'), _('Collection Date'), _('Collection Point'), _('Status')],
                [(l.product_id.display_name, l.disbursement_category_id.name, l.quantity, l.total_amount,
                  l.collection_date, l.collection_point, l.state) for l in app.line_ids],
                _('No disbursement items'),
            )
            rec.inquiry_reports_html = html_table(
                [_('Completed At'), _('Officer'), _('Employee ID'), _('Remarks')],
                [(r.report_date, r.officer_name, r.officer_employee_code, r.content) for r in app.inquiry_report_ids],
                _('No inquiry reports'),
            )
            rec.committee_members_html = html_table(
                [_('Member'), _('Decision'), _('Remarks')],
                [(c.member_id.name, _('Approved') if c.is_approved else _('Rejected') if c.is_rejected else '', c.remarks)
                 for c in app.committee_line_ids],
                _('No committee members'),
            )

    def action_approve(self):
        self.ensure_one()
        application = self.application_id
        if application.state == 'hod_approve':
            if not self.hod_remarks:
                raise ValidationError(_('Please enter HOD Remarks before approval.'))
            application.hod_remarks = self.hod_remarks
            application.action_move_to_committee()
        elif application.state == 'committee_approval':
            if not self.committee_remarks:
                raise ValidationError(_('Please enter Committee Remarks before approval.'))
            application.committee_remarks = self.committee_remarks
            application.action_committee_decision()
        else:
            raise ValidationError(_('Cannot approve from state: %s') % application.state)
        return {'type': 'ir.actions.act_window_close'}
