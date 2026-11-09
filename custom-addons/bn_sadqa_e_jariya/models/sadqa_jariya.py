import json

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

state_selection = [
    ('draft', 'Draft'),
    ('completed', 'Completed'),
    ('form_sent', 'Form Sent'),
    ('form_filled', 'Form Filled'),
    ('send_for_inquiry', 'Send for Inquiry'),
    ('inquiry', 'Inquiry Officer'),
    ('hod_approve', 'HOD Approval'),
    ('committee_approval', 'Committee Approval'),
    ('mem_approve', 'Final Approval'),
    ('approve', 'Approved'),
    ('recurring', 'Recurring'),
    ('disbursed', 'Disbursed'),
    ('reject', 'Rejected'),
    ('return', 'Returned'),
]

order_type_selection = [
    ('one_time', 'One Time'),
    ('recurring', 'Recurring'),
]

# Revert moves one step back, only where nothing was sent to the portal yet or it's all in Odoo:
# the portal contract has no correction / reopening / officer reassignment
REVERT_STATE = {
    'completed': 'draft',
    'hod_approve': 'inquiry',
    'committee_approval': 'hod_approve',
    'mem_approve': 'committee_approval',
}

# Tags required for a corporate/institute Sadqa e Jariya donee.
DONEE_TAGS = (
    'bn_profile_management.donee_partner_category',
    'bn_profile_management.coorporate_institute_partner_category',
    'bn_sadqa_e_jariya.sadqa_jariya_partner_category',
)

# institution type -> portal formKind
FORM_KINDS = {
    'masjid': 'masjid',
    'madrasa': 'madrasa',
}



class SadqaJariya(models.Model):
    _name = 'sadqa.jariya'
    _description = 'Sadqa e Jariya Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Name', default='New', copy=False, readonly=True)
    date = fields.Date('Date', default=fields.Date.context_today)
    order_type = fields.Selection(order_type_selection, string='Order Type')
    state = fields.Selection(state_selection, string='State', default='draft', tracking=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    donee_id = fields.Many2one('res.partner', string='Donee', tracking=True)
    donee_domain = fields.Char('Donee Domain', compute='_compute_donee_domain')
    cnic_no = fields.Char(related='donee_id.cnic_no', string='CNIC No.', store=True)
    employee_category_id = fields.Many2one(
        'hr.employee.category',
        string='Inquiry Officer Category',
        default=lambda self: self.env.ref('bn_sadqa_e_jariya.inquiry_officer_hr_employee_category', raise_if_not_found=False),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Inquiry Officer',
        domain="[('category_ids', 'in', [employee_category_id])]",
        tracking=True,
    )

    institution_category = fields.Selection([
        ('masjid', 'Masjid'),
        ('madrasa', 'Madrasa'),
    ], string='Institution Type', tracking=True)
    subcategory = fields.Char('Subcategory', help="Assistance type sent to the portal, e.g. masjid-food.")
    # Portal form section; follows the Masjid / Madrasa institution category.
    institution_type = fields.Selection([
        ('masjid', 'Masjid'),
        ('madrasa', 'Madrasa'),
    ], string='Institution Type', compute='_compute_institution_type', store=True, readonly=False, tracking=True)

    # Sent to the portal before Send Form (locked for the donee there), then filled from the form
    institute_name = fields.Char('Institution Name')
    address = fields.Char('Institution Address')
    applicant_location_link = fields.Char('Applicant Location Link')
    account_title = fields.Char('Account Title')
    account_number = fields.Char('Account Number')

    # Portal
    portal_login = fields.Char(related='donee_id.sadqa_portal_login', string='Portal Login')
    portal_application_id = fields.Char('Portal Application ID', copy=False, readonly=True)
    portal_status = fields.Char('Portal Status', copy=False, readonly=True)
    portal_report_id = fields.Char('Portal Inquiry Report ID', copy=False, readonly=True)
    form_acknowledged_at = fields.Datetime('Form Imported (ACK)', copy=False, readonly=True)
    inquiry_acknowledged_at = fields.Datetime('Inquiry Imported (ACK)', copy=False, readonly=True)

    committee_remarks = fields.Text('Committee Remarks', tracking=True)
    hod_remarks = fields.Text('HOD Remarks', tracking=True)
    member_remarks = fields.Text('Member Remarks', tracking=True)
    rejection_remarks = fields.Text('Rejection Remarks', tracking=True)

    line_ids = fields.One2many('sadqa.jariya.line', 'application_id', string='Disbursement Items')
    recurring_line_ids = fields.One2many('sadqa.jariya.recurring.line', 'application_id', string='Recurring Lines')
    document_ids = fields.One2many('sadqa.jariya.document', 'application_id', string='Documents')

    inquiry_report_ids = fields.One2many('sadqa.jariya.inquiry.report', 'application_id', string='Inquiry Reports')
    committee_line_ids = fields.One2many('sadqa.jariya.committee.line', 'application_id', string='Committee Members')
    # members already on the tab, left out of the Member dropdown
    committee_member_ids = fields.Many2many('sadqa.jariya.committee.member', compute='_compute_committee_member_ids')
    # the donee's portal form and the inquiry officer's own one
    form_ids = fields.One2many('sadqa.jariya.form', 'application_id', string='Portal Forms')

    previous_application_id = fields.Many2one(
        'sadqa.jariya',
        string='Most Recent Previous Application',
        compute='_compute_previous_application_id',
    )

    @api.model
    def _donee_tag_groups(self):
        """Each Sadqa e Jariya donee tag with the tags of the same name (typed by hand, or kept after a rename)"""
        Tag = self.env['res.partner.category']
        groups = []
        for xmlid in DONEE_TAGS:
            tag = self.env.ref(xmlid, raise_if_not_found=False)
            if tag:
                groups.append(tag | Tag.search([('name', '=ilike', tag.name)]))
        return groups

    @api.model
    def _donee_tag_domain(self, registered=True):
        """Donees with every Sadqa e Jariya tag (Donee, Corporate / Institute, Sadqa-e-Jaria)"""
        domain = [('state', '=', 'register')] if registered else []
        for tags in self._donee_tag_groups():
            domain.append(('category_id', 'in', tags.ids))
        return domain

    @api.depends('committee_line_ids.member_id')
    def _compute_committee_member_ids(self):
        for rec in self:
            rec.committee_member_ids = rec.committee_line_ids.member_id

    def _compute_donee_domain(self):
        domain = json.dumps(self._donee_tag_domain())
        for rec in self:
            rec.donee_domain = domain

    @api.depends('donee_id')
    def _compute_previous_application_id(self):
        for rec in self:
            domain = [('donee_id', '=', rec.donee_id.id), ('state', '!=', 'draft')]
            # _origin also excludes the saved record while the form is being edited
            if rec._origin.id:
                domain.append(('id', '!=', rec._origin.id))
            rec.previous_application_id = self.search(domain, order='date desc, id desc', limit=1) if rec.donee_id else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('sadqa.jariya') or _('New')
        return super().create(vals_list)

    @api.depends('institution_category')
    def _compute_institution_type(self):
        for rec in self:
            rec.institution_type = rec.institution_category or False

    @api.onchange('donee_id')
    def _onchange_donee_id_institution(self):
        # the donee is the institution: its name / address are sent as the form's locked basics
        donee = self.donee_id
        if donee and not self.institute_name:
            self.institute_name = donee.name
        if donee and not self.address:
            self.address = ', '.join(part for part in (donee.street, donee.street2, donee.city) if part) or False

    def _show_notification(self, title, message, type='info'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': type,
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def _auto_disburse_if_all_lines_delivered(self):
        for rec in self.filtered(lambda r: r.state in ('approve', 'recurring')):
            if rec.order_type == 'recurring':
                lines = rec.recurring_line_ids
            else:
                lines = rec.line_ids.filtered(lambda l: l.state != 'cancel')
            if lines and all(l.state == 'disbursed' for l in lines):
                rec.state = 'disbursed'

    def _check_amount_within_hod_limit(self):
        """True when every line is within the HOD approval limit"""
        self.ensure_one()
        hod_group = self.env.ref('bn_sadqa_e_jariya.group_sadqa_jariya_hod', raise_if_not_found=False)
        limit = self.env['sadqa.jariya.approval.limit'].search([
            ('group_id', '=', hod_group.id if hod_group else False),
        ], limit=1)
        if not limit:
            return True
        for line in self.line_ids:
            if line.total_amount > limit.max_amount_limit:
                return False
            if limit.allowed_product_ids and line.product_id not in limit.allowed_product_ids:
                return False
        return True

    def _add_hod_lines(self):
        """Add an HOD line for every HOD product that has none yet (manual lines of the same product are separate)."""
        hod_products = self.env['product.product'].search([('product_tmpl_id.is_sadqa_jariya_hod', '=', True)])
        bank_category = self.env['sadqa.jariya.disbursement.category'].search([('name', '=', 'Bank')], limit=1)
        for record in self:
            new_products = hod_products - record.line_ids.filtered('is_hod').product_id
            if not new_products:
                continue
            self.env['sadqa.jariya.line'].create([{
                'application_id': record.id,
                'product_id': product.id,
                'is_hod': True,
                'disbursement_category_id': bank_category.id,
                'collection_point': 'bank',
                'collection_date': fields.Date.context_today(record),
            } for product in new_products])

    def action_complete(self):
        for record in self:
            missing = [
                label for field_name, label in (
                    ('account_title', _('Account Title')),
                    ('account_number', _('Account Number')),
                )
                if not (record[field_name] or '').strip()
            ]
            if missing:
                raise ValidationError(_('Please enter the following before completing the application: %s') % ', '.join(missing))
        # Disbursement Items come once the portal form is in (Form Filled), see action_send_for_inquiry
        self.write({'state': 'completed'})

    def action_hod_approval(self):
        for record in self:
            if record.state != 'inquiry':
                raise ValidationError(_('Only applications in Inquiry can move to HOD Approval.'))
            record.state = 'hod_approve'
            record._add_hod_lines()
            record.message_post(body=_("Application moved to HOD Approval by %s") % self.env.user.name)

    def action_move_to_committee(self):
        for record in self:
            if record.state != 'hod_approve':
                raise ValidationError(_('Only applications in HOD Approval can move to Committee Approval.'))
            if not record.hod_remarks:
                raise ValidationError(_('Please enter HOD Remarks before moving to Committee Approval!'))
            record.state = 'committee_approval'
            # Every active committee member decides; members can still be removed / added on the Committee Members tab.
            members = self.env['sadqa.jariya.committee.member'].search([])
            self.env['sadqa.jariya.committee.line'].create([{
                'application_id': record.id,
                'member_id': member.id,
            } for member in members - record.committee_line_ids.member_id])
            record.message_post(body=_("Application moved to Committee Approval by %s") % self.env.user.name)

    def action_committee_decision(self):
        for record in self:
            if record.state != 'committee_approval':
                raise ValidationError(_('Only applications in Committee Approval can be completed.'))
            if not record.committee_line_ids:
                raise ValidationError(_('Please add the Committee Members before completing Committee Approval!'))
            pending = record.committee_line_ids.filtered(lambda l: not l.remarks or not (l.is_approved or l.is_rejected))
            if pending:
                raise ValidationError(_('Please enter Remarks and tick Approve or Reject for: %s') % ', '.join(pending.member_id.mapped('name')))
            if not record.committee_remarks:
                raise ValidationError(_('Please enter Committee Remarks before completing Committee Approval!'))
            # Applications within the HOD limit proceed directly; larger ones need Member approval.
            record.state = (
                'approve'
                if record.line_ids and record._check_amount_within_hod_limit()
                else 'mem_approve'
            )

    def action_approve(self):
        for record in self:
            if not record.member_remarks:
                raise ValidationError(_('Please enter Member Remarks!'))
            if not record.line_ids:
                raise ValidationError(_('Please add at least one Disbursement Item before final approval!'))
            record.state = 'approve'
        # HOD lines may already have been disbursed during Final Approval.
        self._auto_disburse_if_all_lines_delivered()
        return self.env.ref('bn_sadqa_e_jariya.action_report_sadqa_jariya_collection').report_action(self)

    def action_reject(self):
        for rec in self:
            if not rec.rejection_remarks:
                raise ValidationError(_('Please enter Rejection Remarks before rejection.'))
            rec.state = 'reject'

    def action_create_recurring_order(self):
        for rec in self:
            if rec.order_type != 'recurring':
                raise ValidationError(_('This request does not belong to recurring order.'))
            for line in rec.line_ids.filtered('recurring_duration'):
                months = int(line.recurring_duration.split('_')[0])
                self.env['sadqa.jariya.recurring.line'].create([{
                    'application_id': rec.id,
                    'collection_date': line.collection_date + relativedelta(months=month),
                    'product_id': line.product_id.id,
                    'currency_id': line.currency_id.id,
                    'analytic_account_id': line.analytic_account_id.id,
                    'disbursement_category_id': line.disbursement_category_id.id,
                    'application_type_id': line.application_type_id.id,
                    'quantity': line.quantity,
                    'collection_point': line.collection_point,
                    'amount': line.total_amount,
                } for month in range(months)])
            rec.state = 'recurring'

    def action_reverse_state(self):
        for rec in self:
            if rec.state not in REVERT_STATE:
                raise UserError(_("[%s] can't be reverted from this state, the portal steps can't be undone.") % rec.display_name)
            rec.state = REVERT_STATE[rec.state]

    def action_view_previous_disbursement(self):
        self.ensure_one()
        if not self.previous_application_id:
            raise UserError(_('No previous application found for this donee.'))
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sadqa.jariya',
            'res_id': self.previous_application_id.id,
            'target': 'current',
        }

    def action_open_review_wizard(self):
        self.ensure_one()
        if self.state not in ['hod_approve', 'committee_approval']:
            raise ValidationError(_('This option is only available in HOD Approval and Committee Approval states.'))
        return {
            'name': _('Review Application'),
            'type': 'ir.actions.act_window',
            'res_model': 'sadqa.jariya.review.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_application_id': self.id},
        }

    def action_print_info(self):
        self.ensure_one()
        if not self.donee_id.exists():
            raise UserError(_("No Donee is set on this application."))
        partner = self.donee_id.sudo()
        return self.env.ref('bn_profile_management.action_profile_management_report').report_action(
            partner, data={'partner_ids': partner.ids}
        )
