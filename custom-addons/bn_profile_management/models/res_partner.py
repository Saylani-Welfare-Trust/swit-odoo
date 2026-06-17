from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import re


cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ---------------------------------------------------------------------
    # Fields
    # ---------------------------------------------------------------------

    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string="Gender", tracking=True)

    religion = fields.Selection([
        ('muslim', 'Muslim'),
        ('non_muslim', 'Non-Muslim'),
        ('syed', 'Syed'),
    ], string="Religion", tracking=True)

    martial_status = fields.Selection([
        ('married', 'Married'),
        ('un_married', 'Unmarried'),
        ('divorce', 'Divorce'),
    ], string="Marital Status", tracking=True)

    has_cnic = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string="Has CNIC", default='yes', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('register', 'Registered'),
        ('reject', 'Rejected'),
        ('change_request', 'Change Request'),
    ], string="State", default='draft', tracking=True)

    area = fields.Many2one('area', string="Area", tracking=True)
    country_code_id = fields.Many2one('res.country', string="Country Code", tracking=True)

    mobile = fields.Char(size=10, string="Mobile", tracking=True)
    cnic_no = fields.Char(size=15, string="CNIC No", tracking=True)
    member_cnic_no = fields.Char(size=15, string="Member CNIC No", tracking=True)
    father_cnic_no = fields.Char(size=15, string="Father's CNIC No", tracking=True)

    surname = fields.Char('Surname', tracking=True)
    next_kin = fields.Char('Next of Kin', tracking=True)
    spouse_name = fields.Char('Spouse Name', tracking=True)
    father_name = fields.Char("Father's Name", tracking=True)

    head_cnic_no = fields.Char(size=15, string="Head CNIC No")
    old_system_id = fields.Char('Old System ID')
    nearest_land_mark = fields.Char('Nearest Landmark')
    reference_remarks = fields.Char('Reference Remarks')
    bank_wallet_account = fields.Char('Bank Wallet Account')

    primary_registration_id = fields.Char('Primary Registration ID')
    secondary_registration_id = fields.Char('Secondary Registration ID')

    cnic_back_image = fields.Binary('CNIC Back Image')
    cnic_front_image = fields.Binary('CNIC Front Image')
    approved_form_file = fields.Binary('Approved Form File')
    reference_letter_file = fields.Binary('Reference Letter File')

    cnic_expiration = fields.Date('CNIC Expiration Date', tracking=True)
    date_of_birth = fields.Date('Date of Birth', tracking=True)
    age = fields.Integer(compute="_compute_age", store=True)

    details = fields.Text('Details', tracking=True)

    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", tracking=True)

    is_change_request = fields.Boolean('Change Request', default=False, tracking=True)
    is_donor = fields.Boolean('Donor', compute="_set_is_donor", store=True)

    donee_required_fields = fields.Boolean('Donee Required Fields', compute="_set_donee_required_fields", store=True)
    welfare_donee_required_fields = fields.Boolean('Welfare Donee Required Fields', compute="_set_welfare_donee_required_fields", store=True)
    welfare_donee_female_required = fields.Boolean('Welfare Donee Female Required', compute="_compute_female_required_override", store=True)

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _get_category_names(self):
        self.ensure_one()
        return set(self.category_id.mapped('name'))

    def _get_category_ids(self):
        return {
            'donee': self.env.ref('bn_profile_management.donee_partner_category').id,
            'donor': self.env.ref('bn_profile_management.donor_partner_category').id,
            'individual': self.env.ref('bn_profile_management.individual_partner_category').id,
            'institution': self.env.ref('bn_profile_management.coorporate_institute_partner_category').id,
        }

    def _format_cnic(self, value):
        if not value:
            return value
        cleaned = re.sub(r'\D', '', value)
        if len(cleaned) >= 13:
            return f"{cleaned[:5]}-{cleaned[5:12]}-{cleaned[12:]}"
        elif len(cleaned) > 5:
            return f"{cleaned[:5]}-{cleaned[5:]}"
        return cleaned

    def _validate_cnic(self, value):
        if value and not re.fullmatch(cnic_pattern, value):
            raise ValidationError(_("Invalid CNIC format (XXXXX-XXXXXXX-X)"))

    # ---------------------------------------------------------------------
    # ONCHANGE CATEGORY
    # ---------------------------------------------------------------------

    @api.onchange('category_id')
    def _onchange_category_id(self):
        for rec in self:
            has_employee_tag = any(
                'employee' in (t.name or '').lower()
                for t in rec.category_id
            )

            if not has_employee_tag:
                continue

            master = self.env['employee.account.master'].search([], limit=1)
            if not master:
                continue

            accounts = self.env['account.account'].search([
                ('code', 'in', [
                    master.advance_account_code,
                    master.petty_cash_account_code
                ])
            ])

            acc_map = {a.code: a.id for a in accounts}

            rec.property_account_receivable_id = acc_map.get(master.advance_account_code)
            rec.property_account_payable_id = acc_map.get(master.petty_cash_account_code)

    # ---------------------------------------------------------------------
    # CONSTRAINTS
    # ---------------------------------------------------------------------

    @api.constrains('mobile')
    def _check_mobile(self):
        for rec in self:
            if rec.mobile and not re.fullmatch(r"\d{10}", rec.mobile):
                raise ValidationError(_("Mobile number must contain 10 digits."))

    @api.constrains('cnic_no', 'member_cnic_no', 'father_cnic_no')
    def _check_cnic(self):
        for rec in self:
            rec._validate_cnic(rec.cnic_no)
            rec._validate_cnic(rec.member_cnic_no)
            rec._validate_cnic(rec.father_cnic_no)

    # ---------------------------------------------------------------------
    # ONCHANGE CNIC (shared logic)
    # ---------------------------------------------------------------------

    def _onchange_cnic_field(self, field_name):
        value = self[field_name]
        if value:
            formatted = self._format_cnic(value)
            self[field_name] = formatted
            self._validate_cnic(formatted)

    @api.onchange('cnic_no')
    def _onchange_cnic(self):
        self._onchange_cnic_field('cnic_no')

    @api.onchange('member_cnic_no')
    def _onchange_member_cnic(self):
        self._onchange_cnic_field('member_cnic_no')

    @api.onchange('father_cnic_no')
    def _onchange_father_cnic(self):
        self._onchange_cnic_field('father_cnic_no')

    # ---------------------------------------------------------------------
    # AGE
    # ---------------------------------------------------------------------

    @api.depends('date_of_birth')
    def _compute_age(self):
        today = fields.Date.today()
        for rec in self:
            rec.age = relativedelta(today, rec.date_of_birth).years if rec.date_of_birth else 0

    # ---------------------------------------------------------------------
    # REQUIRED FIELD LOGIC
    # ---------------------------------------------------------------------

    @api.depends('category_id')
    def _set_donee_required_fields(self):
        for rec in self:
            names = rec._get_category_names()
            rec.donee_required_fields = (
                'Donee' in names and 'Individual' in names
            ) or 'Welfare' in names or 'Medical' in names

    @api.depends('category_id')
    def _set_welfare_donee_required_fields(self):
        for rec in self:
            names = rec._get_category_names()
            rec.welfare_donee_required_fields = (
                'Donee' in names and 'Individual' in names and 'Welfare' not in names
            )

    @api.depends('welfare_donee_required_fields', 'gender')
    def _compute_female_required_override(self):
        for rec in self:
            rec.welfare_donee_female_required = (
                rec.gender != 'female' or rec.welfare_donee_required_fields
            )

    @api.depends('category_id')
    def _set_is_donor(self):
        for rec in self:
            rec.is_donor = 'Donor' in rec._get_category_names()

    # ---------------------------------------------------------------------
    # ACTIONS
    # ---------------------------------------------------------------------

    def action_change_request(self):
        self.write({
            'is_change_request': True,
            'state': 'change_request'
        })

    def action_reject(self):
        self.write({'state': 'reject'})

    def action_print_info(self):
        if self.is_change_request:
            self.state = 'draft'
        self.is_change_request = False
        return self.env.ref(
            'bn_profile_management.action_profile_management_report'
        ).report_action(self)

    # ---------------------------------------------------------------------
    # REGISTRATION
    # ---------------------------------------------------------------------

    def action_register(self):
        Partner = self.env['res.partner']
        today = fields.Date.today()

        for rec in self:

            names = rec._get_category_names()

            is_donee = 'Donee' in names
            is_donor = 'Donor' in names
            is_individual = 'Individual' in names
            is_employee = 'Employee' in names
            is_microfinance = 'Microfinance' in names
            is_welfare = 'Welfare' in names

            # ---------------- validation ----------------
            if is_donee and is_individual and not rec.date_of_birth:
                raise ValidationError(_('Date of Birth required'))

            if rec.age and rec.age < 18 and (is_microfinance or is_welfare):
                raise ValidationError(_('Age restriction for application'))

            if is_donee and rec.cnic_expiration:
                if rec.cnic_expiration < today + relativedelta(years=1):
                    raise ValidationError(_('CNIC expiry must be 1 year ahead'))

            # ---------------- duplicate check (optimized single query) ----------------
            partners = Partner.search([
                ('state', '=', 'register'),
                ('country_code_id', '=', rec.country_code_id.id),
                '|', ('mobile', '=', rec.mobile),
                    ('cnic_no', '=', rec.cnic_no),
            ])

            donee = partners.filtered(lambda p: 'Donee' in p.category_id.mapped('name'))[:1]
            donor = partners.filtered(lambda p: 'Donor' in p.category_id.mapped('name'))[:1]

            # ---------------- linking ----------------
            if is_donee and donor:
                rec.secondary_registration_id = donor.primary_registration_id
            if is_donor and donee:
                rec.secondary_registration_id = donee.primary_registration_id

            # ---------------- sequence ----------------
            if not rec.primary_registration_id:
                seq = self.env['ir.sequence']

                year = str(today.year)[2:]

                if is_donee:
                    s = seq.next_by_code('donee_profile_management') or 'New'
                    check = 2 if rec.gender == 'female' else 3
                    rec.primary_registration_id = f"{year}-{s}-{check}"
                else:
                    s = seq.next_by_code('donor_profile_management') or 'New'
                    check = 8 if is_employee else 6 if is_individual else 7
                    rec.primary_registration_id = f"{year}-{s}-{check}"

            rec.state = 'register'

            if is_microfinance:
                return rec.action_print_microfinance_application()

    # ---------------------------------------------------------------------
    # MICROFINANCE
    # ---------------------------------------------------------------------

    def action_print_microfinance_application(self):
        if 'Microfinance' not in self.category_id.mapped('name'):
            raise ValidationError(_('Only Microfinance allowed'))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Microfinance Scheme',
            'res_model': 'microfinance.application.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_id': self.id},
        }