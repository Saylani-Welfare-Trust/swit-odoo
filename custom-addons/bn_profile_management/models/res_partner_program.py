# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    """Programmes a contact is registered for (the Record Search tags:
    Welfare, Microfinance, Medical ...) and the fields each of them requires."""
    _inherit = 'res.partner'

    # ',name,' list, tested by the profile form: "',cnic_no,' in profile_required_field_names"
    profile_required_field_names = fields.Char(
        'Fields Required to Register', compute='_compute_profile_required_field_names', store=True)
    registered_program_ids = fields.Many2many(
        'res.partner.category', string='Registered In', compute='_compute_registered_program_ids',
        help="Programmes (Record Search tags) this contact has: one tag per module it applied to.")
    registered_program_count = fields.Integer(
        'Programmes', compute='_compute_registered_program_count', store=True,
        help="Number of programmes (Welfare, Microfinance, Medical ...) this contact applied to.")

    @api.depends('category_id', 'category_id.registration_required_field_ids')
    def _compute_profile_required_field_names(self):
        for rec in self:
            names = rec.category_id.mapped('registration_required_field_ids.name')
            rec.profile_required_field_names = ',' + ','.join(names) + ',' if names else False

    @api.depends('category_id', 'category_id.registration_program_code')
    def _compute_registered_program_ids(self):
        for rec in self:
            rec.registered_program_ids = rec.category_id.filtered('registration_program_code')

    # stored (searchable, sortable) unlike the list: its own compute
    @api.depends('category_id', 'category_id.registration_program_code')
    def _compute_registered_program_count(self):
        for rec in self:
            rec.registered_program_count = len(rec.category_id.filtered('registration_program_code'))

    # ------------------------------------------------------------------
    def _program_missing_fields(self):
        """{tag: [field labels]} of the required fields still empty, among
        those the profile form shows this contact (a CNIC field is not asked
        of someone without a CNIC)."""
        self.ensure_one()
        Data = self.env['profile.donation.report.data']
        nodes = {}
        for node in Data._profile_form_arch().iter('field'):
            nodes.setdefault(node.get('name'), node)
        missing = {}
        for tag in self.category_id.filtered('registration_required_field_ids'):
            for field in tag.registration_required_field_ids:
                name = field.name
                if name not in self._fields:
                    continue
                node = nodes.get(name)
                if node is not None and not Data._visible(self, node.get('invisible')):
                    continue
                value = self[name]
                if self._fields[name].type in ('integer', 'float', 'monetary'):
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
                    'fields': '\n'.join('• %s: %s' % (tag.name, ', '.join(labels)) for tag, labels in missing.items()),
                })

    def _register_one(self):
        self._check_program_required_fields()
        return super()._register_one()

    # ------------------------------------------------------------------
    def action_record_search_pick(self):
        """Record Search found several contacts: this is the one. It gets the
        role and programme tags of the search, then opens."""
        self.ensure_one()
        wizard = self.env['confirm.search'].browse(self.env.context.get('confirm_search_id')).exists()
        if not wizard:
            return self._profile_form_popup()
        try:
            with self.env.cr.savepoint():
                wizard._add_search_tags(self)
        except ValidationError as error:
            raise ValidationError(_(
                'The programme tag could not be added to "%(name)s":\n%(error)s\n\n'
                'Several contacts are the same person: merge them first (Contacts, select them, Action > Merge), '
                'then search again.', name=self.display_name, error=error.args[0])) from error
        return wizard._form_action(self)

    def _profile_form_popup(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
            'res_id': self.id,
            'target': 'new',
        }
