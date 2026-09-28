# -*- coding: utf-8 -*-
import ast

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
    profile_page_ids = fields.Many2many(
        'profile.management.page', 'res_partner_category_page_rel', 'category_id', 'page_id',
        string='Form Pages')

    profile_action_id = fields.Many2one('ir.actions.act_window', string='Profile Menu Action', readonly=True, copy=False)
    profile_menu_id = fields.Many2one('ir.ui.menu', string='Profile Menu', readonly=True, copy=False)

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

    @api.model_create_multi
    def create(self, vals_list):
        categories = super().create(vals_list)
        for category in categories:
            if category.is_profile_type:
                category._sync_profile_menu()
        return categories

    def write(self, vals):
        res = super().write(vals)
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

        context = {'default_category_id': [(6, 0, [self.id])]}
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
                if not (k.startswith('show_list_') or k.startswith('show_search_'))
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
