# -*- coding: utf-8 -*-
import ast
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Curated, business-relevant res.partner fields an admin can offer per profile
# type. Deliberately excludes internal compute/helper fields (is_donor,
# donee_required_fields, ...), technical filename Char fields that only pair
# with a Binary field (cnic_front/cnic_back/...), and framework fields.
CURATED_PROFILE_FIELDS = [
    # Identity / contact
    'name', 'image_1920', 'email', 'mobile', 'phone', 'country_code_id',
    'category_id', 'function', 'title', 'parent_id', 'is_company', 'website',
    'company_type', 'vat',
    # Address
    'street', 'street2', 'city', 'state_id', 'zip',
    # Personal details (bn_profile_management)
    'surname', 'gender', 'religion', 'martial_status', 'spouse_name',
    'has_cnic', 'cnic_no', 'cnic_expiration', 'cnic_front_image', 'cnic_back_image',
    'head_cnic_no', 'member_cnic_no', 'reference_letter_file', 'approved_form_file',
    'date_of_birth', 'age', 'father_name', 'father_cnic_no', 'next_kin', 'area',
    'nearest_land_mark', 'reference_remarks', 'bank_wallet_account', 'old_system_id',
    'analytic_account_id', 'details',
    # Registration
    'primary_registration_id', 'secondary_registration_id',
]


# Tokens of a Registration ID Pattern, e.g. '{YY}-{BY-}{SEQ}-{CHECK}'.
REGISTRATION_TOKENS = {
    'YY': 'Registration year, 2 digits (26)',
    'YYYY': 'Registration year, 4 digits (2026)',
    'BY': 'Birth year, 2 digits (90); date of birth required',
    'BY-': 'Birth year + "-" for Individual contacts, nothing otherwise',
    'SEQ': "Next number of the tag's own sequence, padded (00012)",
    'CHECK': 'Check digit, from the Check Digit Rule',
}
TOKEN_RE = re.compile(r'{([A-Z-]+)}')

# What the profile views really showed before they were built from the tag
# (only these fields had a slot). Used once, on upgrade, for tags still on
# the install default "every field", so their screens do not change.
LEGACY_LIST_FIELDS = [
    'primary_registration_id', 'secondary_registration_id', 'old_system_id', 'gender', 'martial_status',
    'street', 'country_code_id', 'mobile', 'email', 'cnic_no', 'date_of_birth', 'age', 'city',
    'analytic_account_id', 'father_name', 'area',
]
LEGACY_SEARCH_FIELDS = [
    'primary_registration_id', 'secondary_registration_id', 'old_system_id', 'cnic_no', 'mobile',
    'email', 'city', 'area', 'analytic_account_id', 'father_name',
]
LEGACY_FORM_ABSENT = ['phone', 'function', 'title', 'parent_id', 'website', 'company_type', 'vat',
                      'analytic_account_id']


class ResPartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    is_profile_type = fields.Boolean(
        'Enable in Profile Management',
        help="When enabled, contacts tagged with this category get a dedicated "
             "menu under Profile Management, with the list/form/search fields "
             "and form pages configured below.")

    profile_list_field_ids = fields.Many2many(
        'ir.model.fields', 'res_partner_category_list_field_rel', 'category_id', 'field_id',
        string='List View Fields', domain=lambda self: self._profile_field_domain())
    profile_form_field_ids = fields.Many2many(
        'ir.model.fields', 'res_partner_category_form_field_rel', 'category_id', 'field_id',
        string='Form View Fields', domain=lambda self: self._profile_field_domain())
    profile_search_field_ids = fields.Many2many(
        'ir.model.fields', 'res_partner_category_search_field_rel', 'category_id', 'field_id',
        string='Search View Fields', domain=lambda self: self._profile_field_domain())
    # The same selections, in the order chosen by the administrator. The
    # Many2many fields above stay the selection itself (kept in sync both ways).
    profile_list_line_ids = fields.One2many('profile.view.field', 'category_id', string='List View',
                                            domain=[('view_type', '=', 'list')], context={'default_view_type': 'list'})
    profile_search_line_ids = fields.One2many('profile.view.field', 'category_id', string='Search View',
                                              domain=[('view_type', '=', 'search')], context={'default_view_type': 'search'})
    profile_form_line_ids = fields.One2many('profile.view.field', 'category_id', string='Form View',
                                            domain=[('view_type', '=', 'form')], context={'default_view_type': 'form'})
    profile_page_ids = fields.Many2many(
        'profile.management.page', 'res_partner_category_page_rel', 'category_id', 'page_id',
        string='Form Pages')

    # Unique ID per tag
    registration_pattern = fields.Char(
        'Registration ID Pattern',
        help="Format of the unique ID a contact gets for this tag when registered. "
             "Tokens: {YY} {YYYY} registration year, {BY} birth year, {BY-} birth year + '-' "
             "for Individuals only, {SEQ} next number, {CHECK} check digit. "
             "Example: WEL-{YYYY}-{SEQ}. Leave empty for tags without an ID.")
    registration_sequence_id = fields.Many2one(
        'ir.sequence', string='ID Sequence', copy=False,
        help="Numbering used by {SEQ}. Created automatically.")
    registration_padding = fields.Integer('Number Length', default=5,
                                          help="Digits of {SEQ}, e.g. 5 gives 00012.")
    registration_check_digit = fields.Selection([
        ('none', 'None'),
        ('donee', 'Donee rule: 0/1 adult F/M, 4/5 minor F/M, 2/3 employee F/M'),
        ('donor', 'Donor rule: 6 individual, 7 organisation, 8 employee'),
    ], string='Check Digit Rule', default='none', required=True)
    registration_example = fields.Char('Example', compute='_compute_registration_example')

    profile_action_id = fields.Many2one('ir.actions.act_window', string='Profile Menu Action', readonly=True, copy=False)
    profile_menu_id = fields.Many2one('ir.ui.menu', string='Profile Menu', readonly=True, copy=False)

    @api.depends('registration_pattern', 'registration_padding', 'registration_check_digit')
    def _compute_registration_example(self):
        for category in self:
            try:
                category.registration_example = category._render_registration_id(
                    sequence_number=12, birth_year=1990, check_digit='1', individual=True,
                ) if category.registration_pattern else False
            except Exception:
                category.registration_example = False

    @api.constrains('registration_pattern', 'registration_check_digit')
    def _check_registration_pattern(self):
        for category in self.filtered('registration_pattern'):
            tokens = TOKEN_RE.findall(category.registration_pattern)
            unknown = [t for t in tokens if t not in REGISTRATION_TOKENS]
            if unknown:
                raise ValidationError(_('Unknown token(s) in the pattern of "%(tag)s": %(tokens)s. Allowed: %(allowed)s') % {
                    'tag': category.name, 'tokens': ', '.join('{%s}' % t for t in unknown),
                    'allowed': ', '.join('{%s}' % t for t in REGISTRATION_TOKENS)})
            if 'SEQ' not in tokens:
                raise ValidationError(_('The pattern of "%s" must contain {SEQ} so every ID is unique.') % category.name)
            if 'CHECK' in tokens and category.registration_check_digit == 'none':
                raise ValidationError(_('The pattern of "%s" uses {CHECK}: choose a Check Digit Rule.') % category.name)

    def _render_registration_id(self, sequence_number, birth_year=None, check_digit='', individual=False):
        self.ensure_one()
        today = fields.Date.context_today(self)
        values = {
            'YY': str(today.year)[2:],
            'YYYY': str(today.year),
            'SEQ': str(sequence_number).zfill(self.registration_padding or 1),
            'CHECK': str(check_digit),
            'BY': str(birth_year)[2:] if birth_year else '',
            'BY-': '%s-' % str(birth_year)[2:] if (birth_year and individual) else '',
        }
        return TOKEN_RE.sub(lambda m: values[m.group(1)], self.registration_pattern)

    def _ensure_registration_sequence(self):
        for category in self.filtered(lambda c: c.registration_pattern and not c.registration_sequence_id):
            category.registration_sequence_id = self.env['ir.sequence'].sudo().create({
                'name': _('Registration ID: %s') % category.name,
                'padding': 0,
                'implementation': 'no_gap',
            })

    @api.model
    def _bn_setup_registration_ids(self):
        """Run on every install/upgrade (data/profile_registration.xml).
        Gives Donor and Donee their pattern - reusing their existing
        sequences, so new IDs continue today's numbering in today's format -
        unless an administrator already configured them, then records the
        IDs already issued as per-tag Registration IDs."""
        presets = [
            ('bn_profile_management.donee_partner_category', '{YY}-{BY-}{SEQ}-{CHECK}', 'donee',
             'bn_profile_management.donee_profile_management_sequence'),
            ('bn_profile_management.donor_partner_category', '{YY}-{SEQ}-{CHECK}', 'donor',
             'bn_profile_management.donor_profile_management_sequence'),
        ]
        for tag_xmlid, pattern, check, sequence_xmlid in presets:
            tag = self.env.ref(tag_xmlid, raise_if_not_found=False)
            sequence = self.env.ref(sequence_xmlid, raise_if_not_found=False)
            if tag and not tag.registration_pattern:
                tag.write({
                    'registration_pattern': pattern,
                    'registration_check_digit': check,
                    'registration_padding': sequence.padding if sequence else 5,
                    'registration_sequence_id': sequence.id if sequence else False,
                })
        self.env['res.partner']._bn_backfill_registration_ids()
        self._bn_setup_dynamic_views()

    @api.model
    def _bn_setup_dynamic_views(self):
        """Views are built from the tag configuration. Tags still on the
        install default (every field everywhere) get what their screens
        really showed until now, then every profile menu is refreshed so it
        passes its tag to the views."""
        Field = self.env['ir.model.fields']
        everything = set(Field.search(self._profile_field_domain()).ids)

        def ids(names):
            return Field.search([('model', '=', 'res.partner'), ('name', 'in', names)]).ids

        for tag in self.search([('is_profile_type', '=', True)]):
            vals = {}
            if everything and set(tag.profile_list_field_ids.ids) >= everything:
                vals['profile_list_field_ids'] = [(6, 0, ids(LEGACY_LIST_FIELDS))]
            if everything and set(tag.profile_search_field_ids.ids) >= everything:
                vals['profile_search_field_ids'] = [(6, 0, ids(LEGACY_SEARCH_FIELDS))]
            if everything and set(tag.profile_form_field_ids.ids) >= everything:
                keep = [f for f in CURATED_PROFILE_FIELDS if f not in LEGACY_FORM_ABSENT]
                vals['profile_form_field_ids'] = [(6, 0, ids(keep))]
            if vals:
                tag.write(vals)
            tag._profile_sync_lines_from_m2m()
            tag._sync_profile_menu()

    @api.model
    def _profile_field_domain(self):
        return [('model', '=', 'res.partner'), ('name', 'in', CURATED_PROFILE_FIELDS)]

    @api.constrains('is_profile_type', 'profile_list_field_ids', 'profile_form_field_ids',
                     'profile_search_field_ids', 'profile_page_ids')
    def _check_profile_configuration(self):
        for category in self:
            if category.is_profile_type and not (
                category.profile_form_field_ids or category.profile_page_ids
            ):
                raise ValidationError(_(
                    'Tag "%s" is enabled for Profile Management but has no form fields or '
                    'pages selected. Please configure what it should show before saving.'
                ) % category.name)

    # ------------------------------------------------------------------
    # Ordered view fields <-> selections
    # ------------------------------------------------------------------
    PROFILE_VIEW_M2M = {'list': 'profile_list_field_ids', 'search': 'profile_search_field_ids',
                        'form': 'profile_form_field_ids'}

    def _profile_view_lines(self, view_type):
        self.ensure_one()
        return self.env['profile.view.field'].search(
            [('category_id', '=', self.id), ('view_type', '=', view_type)])

    def _profile_sync_m2m_from_lines(self):
        """The ordered lines changed: make the selections match."""
        if self.env.context.get('profile_view_sync'):
            return
        for category in self:
            vals = {}
            for view_type, m2m in self.PROFILE_VIEW_M2M.items():
                ids = category._profile_view_lines(view_type).field_id.ids
                if set(ids) != set(category[m2m].ids):
                    vals[m2m] = [(6, 0, ids)]
            if vals:
                category.with_context(profile_view_sync=True).write(vals)

    def _profile_sync_lines_from_m2m(self):
        """The selections changed (code, import, older screens): add the new
        fields at the end, drop the removed ones, keep everyone's position."""
        Line = self.env['profile.view.field'].with_context(profile_view_sync=True)
        order = {name: i for i, name in enumerate(CURATED_PROFILE_FIELDS)}
        for category in self:
            for view_type, m2m in self.PROFILE_VIEW_M2M.items():
                lines = category._profile_view_lines(view_type)
                selected = category[m2m]
                removed = lines.filtered(lambda l: l.field_id not in selected)
                lines -= removed
                removed.with_context(profile_view_sync=True).unlink()
                missing = (selected - lines.field_id).sorted(lambda f: order.get(f.name, 999))
                start = max(lines.mapped('sequence') or [0]) + 1
                Line.create([{'category_id': category.id, 'view_type': view_type, 'field_id': f.id,
                              'sequence': start + i} for i, f in enumerate(missing)])

    @api.model_create_multi
    def create(self, vals_list):
        categories = super().create(vals_list)
        if not self.env.context.get('profile_view_sync'):
            categories._profile_sync_lines_from_m2m()
        categories._ensure_registration_sequence()
        for category in categories:
            if category.is_profile_type:
                category._sync_profile_menu()
        return categories

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('profile_view_sync') and any(m2m in vals for m2m in self.PROFILE_VIEW_M2M.values()):
            self._profile_sync_lines_from_m2m()
        if 'registration_pattern' in vals:
            self._ensure_registration_sequence()
        if 'is_profile_type' in vals or any(
            f in vals for f in ('profile_list_field_ids', 'profile_form_field_ids',
                                'profile_search_field_ids', 'profile_page_ids')
        ):
            for category in self:
                category._sync_profile_menu()
        return res

    def _sync_profile_menu(self):
        """Create/update/hide the dedicated Profile Management menu for this tag."""
        self.ensure_one()
        MasterView = self.env.ref
        if not self.is_profile_type:
            if self.profile_menu_id:
                self.profile_menu_id.active = False
            return

        # profile_tag_view_ref: the list / search views are built from this
        # tag's configuration (models/res_partner_views.py).
        context = {'default_category_id': [(6, 0, [self.id])], 'profile_tag_view_ref': self.id}
        for fname in self.profile_list_field_ids.mapped('name'):
            context['show_list_%s' % fname] = True
        for fname in self.profile_search_field_ids.mapped('name'):
            context['show_search_%s' % fname] = True

        if self.profile_action_id:
            # Merge into whatever context already exists (an action may carry
            # hand-tuned defaults, e.g. default_country_code_id) instead of
            # replacing it wholesale, but first strip any show_list_*/show_search_*
            # keys from a previous sync - otherwise deselecting a field would
            # leave its stale True flag behind and it would never actually hide.
            # `context` is a Char field: read it back as a string, so parse it.
            try:
                existing_context = ast.literal_eval(self.profile_action_id.context or '{}')
            except (ValueError, SyntaxError):
                existing_context = {}
            merged_context = {
                k: v for k, v in existing_context.items()
                if not (k.startswith('show_list_') or k.startswith('show_search_') or k == 'profile_category_id')
            }
            merged_context.update(context)
            self.profile_action_id.write({'name': self.name, 'context': merged_context})
        else:
            action = self.env['ir.actions.act_window'].create({
                'name': self.name,
                'res_model': 'res.partner',
                'view_mode': 'kanban,tree,form',
                'domain': [('category_id', 'in', [self.id])],
                'context': context,
                'search_view_id': MasterView('bn_profile_management.profile_management_view_search').id,
                'view_ids': [
                    (0, 0, {'view_mode': 'kanban', 'view_id': MasterView('bn_profile_management.profile_management_view_kanban').id}),
                    (0, 0, {'view_mode': 'tree', 'view_id': MasterView('bn_profile_management.profile_management_view_tree').id}),
                    (0, 0, {'view_mode': 'form', 'view_id': MasterView('bn_profile_management.profile_management_view_form').id}),
                ],
            })
            self.profile_action_id = action.id

        if self.profile_menu_id:
            self.profile_menu_id.write({'name': self.name, 'active': True})
        else:
            menu = self.env['ir.ui.menu'].create({
                'name': self.name,
                'action': 'ir.actions.act_window,%d' % self.profile_action_id.id,
                'parent_id': MasterView('bn_profile_management.profile_management_menu').id,
            })
            self.profile_menu_id = menu.id
