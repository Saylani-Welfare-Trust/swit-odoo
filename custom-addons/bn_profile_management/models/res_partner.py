import contextlib
import contextvars
import re

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# CNIC regular expression
cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'


general_selection = [
    ('yes', 'Yes'),
    ('no', 'No'),
]

gender_selection = [
    ('male', 'Male'),
    ('female', 'Female'),
]

religion_selection = [
    ('muslim', 'Muslim'),
    ('non_muslim', 'Non-Muslim'),
    ('syed', 'Syed'),
]

martial_status_selection = [
    ('married', 'Married'),
    ('un_married', 'Unmarried'),
    ('divorce', 'Divorce'),
]

state_selection = [
    ('draft', 'Draft'),
    ('register', 'Registered'),
    ('reject', 'Rejected'),
    ('change_request', 'Change Request'),
]


# Fields of a Registered profile that may only change through a Change
# Request: everything shown on the profile form except free-text notes and
# the branch. category_id and the registration IDs are included.
PROFILE_LOCKED_FIELDS = (
    'name', 'image_1920', 'email', 'mobile', 'phone', 'country_code_id',
    'category_id', 'function', 'title', 'parent_id', 'is_company', 'company_type',
    'website', 'vat', 'street', 'street2', 'city', 'state_id', 'zip', 'country_id',
    'surname', 'gender', 'religion', 'martial_status', 'spouse_name',
    'has_cnic', 'cnic_no', 'cnic_expiration', 'cnic_front_image', 'cnic_back_image',
    'head_cnic_no', 'member_cnic_no', 'reference_letter_file', 'approved_form_file',
    'date_of_birth', 'father_name', 'father_cnic_no', 'next_kin', 'area',
    'nearest_land_mark', 'bank_wallet_account', 'old_system_id',
    'primary_registration_id', 'secondary_registration_id',
)

# Set while a profile workflow method runs. A Python ContextVar, not an Odoo
# context key: an RPC client can put any key in the context, but cannot set
# server-side Python state.
_PROFILE_TRANSITION = contextvars.ContextVar('bn_profile_transition', default=False)


@contextlib.contextmanager
def profile_transition():
    token = _PROFILE_TRANSITION.set(True)
    try:
        yield
    finally:
        _PROFILE_TRANSITION.reset(token)


class ResPartner(models.Model):
    _inherit = 'res.partner'


    gender = fields.Selection(selection=gender_selection, string="Gender", tracking=True)
    religion = fields.Selection(selection=religion_selection, string="Religion", tracking=True)
    martial_status = fields.Selection(selection=martial_status_selection, string="Martial Status", tracking=True)
    has_cnic = fields.Selection(selection=general_selection, string="Has CNIC", default='yes', tracking=True)
    state = fields.Selection(selection=state_selection, string="State", default='draft', tracking=True)
    
    area = fields.Many2one('area', string="Area", tracking=True)
    # No size=: a size silently truncates longer input (03001234567 was
    # stored as 0300123456). _check_mobile_number rejects it instead.
    mobile = fields.Char(tracking=True)
    surname = fields.Char('Surname', tracking=True)
    cnic_no = fields.Char('CNIC No.', tracking=True, size=15)
    next_kin = fields.Char('Next Kin', tracking=True)
    spouse_name = fields.Char('Spouse Name', tracking=True)
    father_name = fields.Char('Father Name', tracking=True)
    head_cnic_no = fields.Char('Head CNIC No.', tracking=True, size=15)
    old_system_id = fields.Char('Old System ID', tracking=True)
    member_cnic_no = fields.Char('Member CNIC No.', tracking=True, size=15)
    father_cnic_no = fields.Char('Father CNIC No.', tracking=True, size=15)
    nearest_land_mark = fields.Char('Nearest Land Mark', tracking=True)
    reference_remarks = fields.Char('Reference / Remarks', tracking=True)
    bank_wallet_account = fields.Char('Bank / Wallet Account', tracking=True)
    primary_registration_id = fields.Char('Primary Registration ID', tracking=True)
    secondary_registration_id = fields.Char('Secondary Registration ID', tracking=True)

    cnic_back = fields.Char('CNIC Back', tracking=True)
    cnic_front = fields.Char('CNIC Front', tracking=True)
    approved_form = fields.Char('Approved Form', tracking=True)
    reference_letter = fields.Char('Reference Letter', tracking=True)

    cnic_back_image = fields.Binary('CNIC Back Image')
    cnic_front_image = fields.Binary('CNIC Front Image')
    approved_form_file = fields.Binary('Approved Form File')
    reference_letter_file = fields.Binary('Reference Letter File')

    cnic_expiration = fields.Date('CNIC Expiration', tracking=True)
    date_of_birth = fields.Date('Date Of Birth', tracking=True)
    
    details = fields.Text('Details', tracking=True)

    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    country_code_id = fields.Many2one('res.country', string="Phone Code")

    # Not stored: a stored age is computed once and never ages.
    age = fields.Integer('Age', compute="_compute_age")

    is_change_request = fields.Boolean('Is Change Request')
    is_donor = fields.Boolean('Is Donor', compute="_set_is_donor", store=True)
    donee_required_fields = fields.Boolean('Donee Required Fields', compute="_set_donee_required_fields", store=True)
    welfare_donee_required_fields = fields.Boolean('Welfare Donee Required Fields', compute="_set_welfare_donee_required_fields", store=True)
    welfare_donee_female_required = fields.Boolean('Welfare Donee', compute="_compute_female_required_override", store=True)

    registration_ids = fields.One2many('res.partner.registration', 'partner_id', string='Registration IDs')
    pending_registration_tags = fields.Char(
        'Tags Awaiting Registration', compute='_compute_pending_registration',
        help="Tags with a Registration ID Pattern for which this contact has no ID yet.")
    has_pending_registration = fields.Boolean(compute='_compute_pending_registration')

    # Profile Management: which form fields/pages this contact should show,
    # as the union of every enabled tag it carries. Wrapped in commas so a
    # view can test membership with "',fieldname,' in profile_visible_form_field_names".
    profile_visible_form_field_names = fields.Char(
        'Profile Visible Fields', compute='_compute_profile_visibility', store=True)
    profile_visible_page_names = fields.Char(
        'Profile Visible Pages', compute='_compute_profile_visibility', store=True)

    @api.depends('category_id', 'category_id.is_profile_type',
                 'category_id.profile_form_field_ids', 'category_id.profile_page_ids')
    def _compute_profile_visibility(self):
        for rec in self:
            categories = rec.category_id.filtered('is_profile_type')
            field_names = categories.mapped('profile_form_field_ids.name')
            page_names = categories.mapped('profile_page_ids.technical_name')
            rec.profile_visible_form_field_names = ',' + ','.join(field_names) + ','
            rec.profile_visible_page_names = ',' + ','.join(page_names) + ','

    @api.depends('category_id', 'category_id.registration_pattern', 'registration_ids.category_id', 'state')
    def _compute_pending_registration(self):
        for rec in self:
            pending = rec._pattern_tags_without_id() if rec.state == 'register' else rec.browse()
            rec.pending_registration_tags = ', '.join(pending.mapped('name'))
            rec.has_pending_registration = bool(pending)

    def _pattern_tags_without_id(self):
        self.ensure_one()
        done = self.registration_ids.mapped('category_id')
        return self.category_id.filtered(lambda c: c.registration_pattern) - done

    # ------------------------------------------------------------------
    # One contact per person
    # ------------------------------------------------------------------
    def _is_profile_contact(self):
        self.ensure_one()
        return any(self.category_id.mapped('is_profile_type'))

    @api.constrains('cnic_no', 'mobile', 'country_code_id', 'category_id', 'active')
    def _check_duplicate_person(self):
        """A person has ONE contact; their roles are tags on it. Refuse a
        second contact with the same CNIC (any contact), or the same mobile +
        phone code (between profile contacts)."""
        for rec in self.filtered('active'):
            existing = self.browse()
            reason = ''
            if rec.cnic_no:
                existing = self.with_context(active_test=True).search(
                    [('cnic_no', '=', rec.cnic_no), ('id', '!=', rec.id)], limit=1)
                reason = _('CNIC %s') % rec.cnic_no
            if not existing and rec.mobile and rec._is_profile_contact():
                candidates = self.search([
                    ('mobile', '=', rec.mobile), ('country_code_id', '=', rec.country_code_id.id),
                    ('id', '!=', rec.id),
                ])
                existing = candidates.filtered(lambda p: p._is_profile_contact())[:1]
                reason = _('mobile %s') % rec.mobile
            if existing:
                ids = ', '.join(existing.registration_ids.mapped('code')) or existing.primary_registration_id or _('not registered')
                raise ValidationError(_(
                    'This person already exists as "%(name)s" (%(ids)s), same %(reason)s.\n'
                    'Open that contact (e.g. with Record Search) and add the tag to it '
                    'instead of creating a second contact.'
                ) % {'name': existing.display_name, 'ids': ids, 'reason': reason})

    @api.model_create_multi
    def create(self, vals_list):
        pakistan_id = self.env.ref('base.pk').id
        for vals in vals_list:
            if not vals.get('country_code_id'):
                vals['country_code_id'] = pakistan_id
        return super().create(vals_list)  
        
    def write(self, vals):
        if not self.env.su and not _PROFILE_TRANSITION.get():
            if 'state' in vals:
                raise UserError(_('The status of a profile can only be changed with its buttons '
                                  '(Register, Reject, Change Request ...).'))
            self._check_profile_lock(vals)
        if 'mobile' in vals and vals.get('mobile'):
            mobile = vals['mobile']
            for rec in self:
                category_names = set(rec.category_id.mapped('name'))
                is_donee = 'Donee' in category_names
                is_donor = 'Donor' in category_names

                domain = [
                    ('mobile', '=', mobile),
                    ('state', '=', 'register'),
                    ('id', '!=', rec.id),
                ]

                # Only compare within the same category so Donor/Donee
                # can legitimately share a mobile number
                if is_donee and not is_donor:
                    domain.append(('category_id.name', '=', 'Donee'))
                elif is_donor and not is_donee:
                    domain.append(('category_id.name', '=', 'Donor'))

                existing = self.search(domain)
                if existing:
                    raise ValidationError(
                        "A Partner with the same Mobile No. already exists in the System."
                    )
        return super(ResPartner, self).write(vals)

    def _check_profile_lock(self, vals):
        """A Registered profile only changes through a Change Request."""
        locked = [name for name in PROFILE_LOCKED_FIELDS if name in vals and name in self._fields]
        if not locked:
            return
        for rec in self.filtered(lambda p: p.state == 'register'):
            changed = []
            for name in locked:
                field = rec._fields[name]
                try:
                    new = field.convert_to_cache(vals[name], rec)
                    old = field.convert_to_cache(rec[name], rec)
                except Exception:
                    new, old = vals[name], None
                if name == 'category_id' and isinstance(new, tuple) and set(old) <= set(new):
                    # Adding tags is allowed (a registered donee who also
                    # donates gets the Donor tag); removing them is not.
                    continue
                if new != old:
                    changed.append(field.string)
            if changed:
                raise UserError(_(
                    '"%(name)s" is a Registered profile. To change %(fields)s, '
                    'use the Change Request button first.'
                ) % {'name': rec.display_name, 'fields': ', '.join(changed)})

    def _profile_write(self, vals):
        """Write as a legitimate profile workflow step (bypasses the lock)."""
        with profile_transition():
            return self.write(vals)

    @api.onchange('category_id')
    def _onchange_category_id(self):
        for rec in self:
            has_employee_tag = any(
                'employee' in (tag.name or '').lower()
                for tag in rec.category_id
            )

            if has_employee_tag:
                Account = self.env['account.account']
                company_domain = [('company_id', '=', (rec.company_id or self.env.company).id)]
                advance_account_id = Account.search([('code', '=', '102501001')] + company_domain, limit=1).id
                petty_cash_account_id = Account.search([('code', '=', '202101010')] + company_domain, limit=1).id

                rec.property_account_receivable_id = advance_account_id
                rec.property_account_payable_id = petty_cash_account_id

    @api.constrains('mobile')
    def _check_mobile_number(self):
        for rec in self:
            if rec.mobile:
                if not re.fullmatch(r"\d{10}", rec.mobile):
                    raise ValidationError(
                        "Mobile number must contain exactly 10 digits."
                    )

    @api.depends('name', 'category_id')
    def _set_welfare_donee_required_fields(self):
        for rec in self:
            rec.welfare_donee_required_fields = False
            cat_names = rec.category_id.mapped('name')
            is_donee_individual = 'Donee' in cat_names and 'Individual' in cat_names
            is_welfare = 'Welfare' in cat_names
            if is_donee_individual and not is_welfare:
                rec.welfare_donee_required_fields = True
            
    @api.depends('welfare_donee_required_fields', 'gender')
    def _compute_female_required_override(self):
        for rec in self:
            # For welfare-sensitive fields, if gender is female, required = True
            # (overrides the welfare exclusion)
            rec.welfare_donee_female_required = rec.gender != 'female' or rec.welfare_donee_required_fields

    @api.depends('name', 'category_id')
    def _set_donee_required_fields(self):
        for rec in self:
            rec.donee_required_fields = False

            if 'Donee' in rec.category_id.mapped('name') and 'Individual' in rec.category_id.mapped('name'):
                rec.donee_required_fields = True
    
    @api.depends('name', 'category_id')
    def _set_is_donor(self):
        for rec in self:
            rec.is_donor = False

            if 'Donor' in rec.category_id.mapped('name'):
                rec.is_donor = True

    @api.depends('date_of_birth')
    def _compute_age(self):
        today = fields.Date.today()
        for record in self:
            # Completed years: someone born on 31 Dec 2008 is 17 until 31 Dec 2026.
            record.age = relativedelta(today, record.date_of_birth).years if record.date_of_birth else 0

    @api.constrains('cnic_no')
    def _check_cnic_no_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(cnic_pattern, record.cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    def is_valid_cnic_format(self, cnic):
        return bool(re.fullmatch(r'\d{5}-\d{7}-\d', cnic))

    @api.onchange('cnic_no')
    def _onchange_cnic_no(self):
        if self.cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic_no)
            if len(cleaned_cnic) >= 13:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

            if not self.is_valid_cnic_format(self.cnic_no):
                raise ValidationError('Invalid CNIC No. format ( acceptable format XXXXX-XXXXXXX-X )')

    @api.constrains('member_cnic_no')
    def _check_member_cnic_no_format(self):
        for record in self:
            if record.member_cnic_no:
                if not re.match(cnic_pattern, record.member_cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.member_cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('member_cnic_no')
    def _onchange_member_cnic_no(self):
        if self.member_cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.member_cnic_no)
            if len(cleaned_cnic) >= 13:
                self.member_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.member_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

            
            if not self.is_valid_cnic_format(self.member_cnic_no):
                raise ValidationError('Invalid CNIC No. format ( acceptable format XXXXX-XXXXXXX-X )')
    
    @api.constrains('father_cnic_no')
    def _check_father_cnic_no_format(self):
        for record in self:
            if record.father_cnic_no:
                if not re.match(cnic_pattern, record.father_cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.father_cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('father_cnic_no')
    def _onchange_father_cnic_no(self):
        if self.father_cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.father_cnic_no)
            if len(cleaned_cnic) >= 13:
                self.father_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.father_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

            
            if not self.is_valid_cnic_format(self.father_cnic_no):
                raise ValidationError('Invalid CNIC No. format ( acceptable format XXXXX-XXXXXXX-X )')
    
    @api.onchange('date_of_birth')
    def _onchange_date_of_birth(self):
        if self.date_of_birth:
            if self.date_of_birth.year == fields.Date.today().year or self.date_of_birth.year > fields.Date.today().year:
                raise ValidationError(str(f'Invalid Date of Birth...'))

    def action_print_info(self):
        if self.is_change_request:
            self._profile_write({'state': 'draft', 'is_change_request': False})
        return self.env.ref('bn_profile_management.action_profile_management_report').report_action(self)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _check_profile_state(self, allowed, action):
        labels = dict(state_selection)
        for rec in self:
            if rec.state not in allowed:
                raise UserError(_(
                    '"%(action)s" is not possible for "%(name)s" in status "%(state)s".'
                ) % {'action': action, 'name': rec.display_name, 'state': labels.get(rec.state, rec.state)})

    def action_welfare_application(self):
        """Create the Welfare application of a newly registered welfare donee
        (module bn_welfare, not part of this repository)."""
        self.ensure_one()
        if 'welfare' not in self.env:
            raise UserError(_(
                'Cannot register "%s" for Welfare: the Welfare module is not installed.'
            ) % self.display_name)
        Welfare = self.env['welfare']
        existing = Welfare.search([('donee_id', '=', self.id)], limit=1)
        if existing:
            return existing
        return Welfare.create({
            'donee_id': self.id,
            'is_individual': 'Individual' in self.category_id.mapped('name'),
        })

    def _find_registered_duplicate(self, category, cnic=False, mobile=False, country_check=True):
        """Registered partner of ``category`` sharing the given CNIC or mobile.
        Only values that are actually filled in are compared: two people
        without a CNIC are not duplicates of each other."""
        self.ensure_one()
        alternatives = []
        if cnic:
            alternatives.append([('cnic_no', '=', cnic)])
        if mobile:
            mobile_domain = [('mobile', '=', mobile)]
            if country_check:
                mobile_domain.append(('country_code_id', '=', self.country_code_id.id))
            alternatives.append(mobile_domain)
        if not alternatives:
            return self.browse()
        from odoo.osv import expression
        domain = expression.AND([
            [('state', '=', 'register'), ('category_id.name', '=', category), ('id', '!=', self.id)],
            expression.OR(alternatives),
        ])
        return self.search(domain, limit=1)

    def _register_one(self):
        """Validate and register one profile. Returns True when it is a
        Microfinance donee (the caller may then open the scheme wizard)."""
        self.ensure_one()
        rec = self
        today = fields.Date.today()
        category_names = set(rec.category_id.mapped('name'))

        is_donee = 'Donee' in category_names
        is_donor = 'Donor' in category_names
        is_individual = 'Individual' in category_names
        is_employee = 'Employee' in category_names
        is_microfinance = 'Microfinance' in category_names
        is_welfare = 'Welfare' in category_names

        # -------------------------
        # Validations
        # -------------------------
        if is_donee and is_individual and not rec.date_of_birth:
            raise ValidationError('Please specify your Date of Birth...')

        if (is_microfinance or is_welfare) and rec.date_of_birth and rec.age < 18:
            if is_microfinance:
                raise ValidationError(
                    'Cannot register the Person for Microfinance as his/her age is below 18.'
                )
            raise ValidationError(
                'Cannot register the Person for Welfare as his/her age is below 18.'
            )

        if is_donee and rec.cnic_expiration:
            if rec.cnic_expiration < (today + relativedelta(years=1)):
                raise ValidationError(
                    'CNIC expiry date should be minimum one year from the date of application. '
                    'Please renew your CNIC before registration.'
                )

        # -------------------------
        # Duplicate & Linking Logic
        # -------------------------
        vals = {}
        if is_donee:
            if rec._find_registered_duplicate('Donee', cnic=rec.cnic_no, mobile=rec.mobile):
                raise ValidationError(
                    'A Donee with same CNIC or Mobile No. already exist in the System.'
                )

        elif is_donor:
            if rec._find_registered_duplicate('Donor', mobile=rec.mobile):
                raise ValidationError(
                    'A Donor with same Mobile No. already exist in the System.'
                )

        if is_welfare and 'welfare' not in self.env:
            raise UserError(_(
                'Cannot register "%s" for Welfare: the Welfare module is not installed.'
            ) % rec.display_name)

        # -------------------------
        # One Registration ID per tag, in the tag's own pattern
        # -------------------------
        new_ids = rec._generate_registration_ids(is_individual=is_individual, is_employee=is_employee)
        rec.invalidate_recordset(['registration_ids'])
        by_tag = {reg.category_id.name: reg.code for reg in rec.registration_ids}
        main = by_tag.get('Donee') if is_donee else by_tag.get('Donor')
        if main and not rec.primary_registration_id:
            vals['primary_registration_id'] = main
        elif not rec.primary_registration_id and new_ids:
            vals['primary_registration_id'] = new_ids[0]
        if is_donee and is_donor and by_tag.get('Donor'):
            # Same person, both roles: the Donor ID is the secondary one.
            vals['secondary_registration_id'] = by_tag['Donor']

        # -------------------------
        # Final Actions
        # -------------------------
        vals.update(state='register', is_change_request=False)
        rec._profile_write(vals)

        if is_welfare:
            rec.action_welfare_application()

        return is_microfinance

    def _check_digit(self, rule, is_individual, is_employee):
        if rule == 'donee':
            if is_employee:
                return 2 if self.gender == 'female' else 3
            if self.date_of_birth and self.age >= 18:
                return 0 if self.gender == 'female' else 1
            return 4 if self.gender == 'female' else 5
        if rule == 'donor':
            return 8 if is_employee else 6 if is_individual else 7
        return ''

    def _generate_registration_ids(self, is_individual, is_employee):
        """Create the missing Registration ID of every tag with a pattern."""
        self.ensure_one()
        created = []
        for tag in self._pattern_tags_without_id():
            if '{BY}' in tag.registration_pattern and not self.date_of_birth:
                raise ValidationError(_('The ID of tag "%s" needs the Date of Birth.') % tag.name)
            tag._ensure_registration_sequence()
            number = tag.registration_sequence_id.sudo().next_by_id()
            code = tag._render_registration_id(
                sequence_number=number,
                birth_year=self.date_of_birth.year if self.date_of_birth else None,
                check_digit=self._check_digit(tag.registration_check_digit, is_individual, is_employee),
                individual=is_individual,
            )
            self.env['res.partner.registration'].sudo().create({
                'partner_id': self.id, 'category_id': tag.id, 'code': code})
            created.append(code)
        return created

    @api.model
    def _bn_backfill_registration_ids(self):
        """Record IDs issued before per-tag IDs existed (idempotent)."""
        Registration = self.env['res.partner.registration'].sudo()
        tags = {name: self.env.ref('bn_profile_management.%s_partner_category' % name.lower(), raise_if_not_found=False)
                for name in ('Donee', 'Donor')}
        partners = self.sudo().with_context(active_test=False).search([
            ('primary_registration_id', '!=', False), ('registration_ids', '=', False)])
        for partner in partners:
            names = partner.category_id.mapped('name')
            tag = tags['Donee'] if 'Donee' in names else tags['Donor'] if 'Donor' in names else None
            if not tag or Registration.search_count([('category_id', '=', tag.id), ('code', '=', partner.primary_registration_id)]):
                continue
            Registration.create({'partner_id': partner.id, 'category_id': tag.id,
                                 'code': partner.primary_registration_id, 'date': partner.write_date.date()})

    def action_register(self):
        self._check_can_register()
        microfinance = self.browse()
        for rec in self:
            if rec._register_one():
                microfinance |= rec
        return self._profile_after_register(microfinance)

    def _profile_after_register(self, microfinance):
        """Action returned by Register. ``microfinance``: the Microfinance donees
        just registered (bn_microfinance then offers their application)."""
        return True

    def action_bulk_register_donee(self):
        """Register the selected profiles without opening any wizard
        (also for Microfinance donees)."""
        self._check_can_register()
        for rec in self:
            rec._register_one()
        return True

    def _check_can_register(self):
        """Draft / Change Request, or Registered with a newly added tag that
        has no ID yet (e.g. a registered donee who now also donates)."""
        for rec in self:
            if rec.state == 'register' and rec._pattern_tags_without_id():
                continue
            rec._check_profile_state(('draft', 'change_request'), _('Register'))

    def action_change_request(self):
        self._check_profile_state(('register',), _('Change Request'))
        self._profile_write({'is_change_request': True, 'state': 'change_request'})
        return True

    def action_reject(self):
        self._check_profile_state(('draft', 'change_request'), _('Reject'))
        self._profile_write({'state': 'reject'})
        return True

    def action_reset_to_draft(self):
        self._check_profile_state(('reject',), _('Reset to Draft'))
        self._profile_write({'state': 'draft', 'is_change_request': False})
        return True

