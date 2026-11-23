# -*- coding: utf-8 -*-
"""Record Search programmes (from the Development branch), alongside the
registration types of this Profile Management (Welfare, Microfinance,
Medical, Student), which keep working as before.

A tag with a Record Search code is a programme: a module's Record Search
menu passes that code (e.g. Sadqa e Jariya: default_program_code
'sadqa_e_jariya'), and the contact found or created gets the role and the
programme tags. The tag also says which fields must be filled before such a
contact is registered, and which menus of the module follow it (hidden while
the programme is disabled)."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    registration_program_code = fields.Char(
        'Record Search Code', copy=False,
        help="Makes this tag a programme offered by Record Search. A module's Record Search "
             "menu passes this code (e.g. sadqa_e_jariya). Leave empty for other tags.")
    registration_program_active = fields.Boolean(
        'Programme Enabled', default=True,
        help="Off: the programme's menus in its module are hidden and Record Search no longer "
             "offers it. On again: they come back.")
    program_menu_ids = fields.Many2many(
        'ir.ui.menu', 'res_partner_category_program_menu_rel', 'category_id', 'menu_id',
        string='Programme Menus', readonly=True, copy=False,
        help="Menus of the module of this programme, linked on install / upgrade.")
    registration_role = fields.Selection([('donee', 'Donee'), ('donor', 'Donor')], string='Registers as',
                                         default='donee')
    registration_kind = fields.Selection([
        ('choose', 'Chosen at the search'),
        ('individual', 'Individual'),
        ('institution', 'Corporate / Institute'),
    ], string='Contact Kind', default='choose',
        help="Individual / Corporate-Institute tag given with the programme.")
    registration_required_field_ids = fields.Many2many(
        'ir.model.fields', 'res_partner_category_required_field_rel', 'category_id', 'field_id',
        string='Required to Register', domain=[('model', '=', 'res.partner')],
        help="Fields that must be filled before a contact with this tag can be registered.")

    _sql_constraints = [
        ('registration_program_code_uniq', 'unique(registration_program_code)',
         'Another tag already uses this Record Search code.'),
    ]

    @api.model
    def _record_search_program(self, code):
        """The programme tag of a Record Search code (empty when unknown)."""
        if not code:
            return self.browse()
        return self.sudo().search([('registration_program_code', '=', code)], limit=1).sudo(False)

    @api.model
    def _link_program_menus(self, code, menu_xmlids):
        """Install / upgrade of a programme module: its menus follow the tag of
        its Record Search code (shown while the programme is enabled)."""
        tag = self._record_search_program(code).sudo()
        if not tag:
            return
        menus = self.env['ir.ui.menu'].sudo()
        for xmlid in menu_xmlids:
            menus |= self.env.ref(xmlid, raise_if_not_found=False) or self.env['ir.ui.menu']
        if menus - tag.program_menu_ids:
            tag.program_menu_ids = [(4, menu.id) for menu in menus]
        tag._sync_program_menus()

    def _sync_program_menus(self):
        for tag in self.sudo():
            show = bool(tag.registration_program_code and tag.registration_program_active)
            menus = tag.with_context(active_test=False).program_menu_ids
            changed = menus.filtered(lambda m: m.active != show)
            if changed:
                changed.write({'active': show})

    def write(self, vals):
        res = super().write(vals)
        if {'registration_program_active', 'registration_program_code'} & set(vals):
            self._sync_program_menus()
        return res


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ',name,' list, tested by profile forms: "',cnic_no,' in profile_required_field_names"
    profile_required_field_names = fields.Char(
        'Fields Required to Register', compute='_compute_profile_required_field_names', store=True)
    registered_program_ids = fields.Many2many(
        'res.partner.category', string='Registered In', compute='_compute_registered_program_ids',
        help="Programmes (Record Search tags) this contact has.")
    registered_program_count = fields.Integer(
        'Programmes', compute='_compute_registered_program_count', store=True)

    @api.depends('category_id', 'category_id.registration_required_field_ids')
    def _compute_profile_required_field_names(self):
        for rec in self:
            names = rec.category_id.mapped('registration_required_field_ids.name')
            rec.profile_required_field_names = ',' + ','.join(names) + ',' if names else False

    @api.depends('category_id', 'category_id.registration_program_code')
    def _compute_registered_program_ids(self):
        for rec in self:
            rec.registered_program_ids = rec.category_id.filtered('registration_program_code')

    @api.depends('category_id', 'category_id.registration_program_code')
    def _compute_registered_program_count(self):
        for rec in self:
            rec.registered_program_count = len(rec.category_id.filtered('registration_program_code'))

    def _program_missing_fields(self):
        """{tag: [field labels]} of the fields a programme requires that are still empty."""
        self.ensure_one()
        missing = {}
        for tag in self.category_id.filtered('registration_required_field_ids'):
            for field in tag.registration_required_field_ids:
                if field.name not in self._fields:
                    continue
                value = self[field.name]
                if self._fields[field.name].type in ('integer', 'float', 'monetary'):
                    filled = value not in (False, None)
                else:
                    filled = bool(value)
                if not filled:
                    missing.setdefault(tag, []).append(field.field_description)
        return missing

    def _check_program_required_fields(self):
        for rec in self:
            missing = rec._program_missing_fields()
            if missing:
                raise ValidationError(_('%(contact)s cannot be registered yet. Please fill in:\n%(fields)s') % {
                    'contact': rec.display_name,
                    'fields': '\n'.join('• %s: %s' % (tag.name, ', '.join(labels))
                                        for tag, labels in missing.items()),
                })

    def action_register(self):
        self._check_program_required_fields()
        return super().action_register()
