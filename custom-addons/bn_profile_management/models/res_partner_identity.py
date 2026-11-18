# -*- coding: utf-8 -*-
import re

from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    """One contact per person, whatever module or screen creates it.

    A person is identified by CNIC, Registration ID or mobile number (with its
    phone code). Every module that creates contacts goes through
    _find_or_create_person: an existing person is reused and only gets the
    missing tags. The constraint below refuses a second contact for the same
    person from any other path (Contacts app, imports, RPC ...)."""
    _inherit = 'res.partner'

    @api.model
    def _normalize_mobile(self, mobile):
        """The 10-digit form stored on contacts (3001234567): drops spaces,
        dashes, a leading 0 or the country code."""
        digits = re.sub(r'\D', '', mobile or '')
        return digits[-10:] if len(digits) >= 10 else (mobile or '').strip()

    @api.model
    def _find_person(self, mobile=None, country=None, cnic=None, registration_id=None):
        """The existing contact of a person: by CNIC, then Registration ID,
        then mobile + phone code. Empty when none."""
        Partner = self.sudo().with_context(active_test=True)
        if cnic:
            partner = Partner.search([('cnic_no', '=', cnic.strip())], limit=1)
            if partner:
                return partner.sudo(False)
        if registration_id:
            code = registration_id.strip()
            partner = Partner.search(['|', ('registration_ids.code', '=', code),
                                      ('primary_registration_id', '=', code)], limit=1)
            if partner:
                return partner.sudo(False)
        if mobile:
            country_id = country.id if hasattr(country, 'id') else country
            partner = Partner.search([
                ('mobile', '=', self._normalize_mobile(mobile)), ('parent_id', '=', False),
                ('country_code_id', '=', country_id or self.env.ref('base.pk').id)], limit=1)
            if partner:
                return partner.sudo(False)
        return self.browse()

    def _add_person_tags(self, tags):
        """Give an existing person the tags of a new role / programme (never
        removes any)."""
        tag_ids = tags.ids if hasattr(tags, 'ids') else list(tags or [])
        for partner in self:
            missing = [tag for tag in tag_ids if tag not in partner.category_id.ids]
            if missing:
                partner.sudo()._profile_write({'category_id': [(4, tag) for tag in missing]})

    @api.model
    def _find_or_create_person(self, vals, tags=()):
        """The contact of the person described by ``vals``: the existing one
        (with the missing ``tags`` added), else a new one."""
        vals = dict(vals)
        if vals.get('mobile'):
            vals['mobile'] = self._normalize_mobile(vals['mobile'])
        partner = self._find_person(mobile=vals.get('mobile'), country=vals.get('country_code_id'),
                                    cnic=vals.get('cnic_no'))
        if partner:
            partner._add_person_tags(tags)
            return partner
        tag_ids = tags.ids if hasattr(tags, 'ids') else list(tags or [])
        if tag_ids:
            vals['category_id'] = [(6, 0, list(set(tag_ids) | set(self._category_ids_of(vals))))]
        return self.create(vals)

    @api.model
    def _category_ids_of(self, vals):
        ids = set()
        for command in vals.get('category_id') or []:
            if isinstance(command, (list, tuple)) and command[0] == 6:
                ids |= set(command[2])
            elif isinstance(command, (list, tuple)) and command[0] == 4:
                ids.add(command[1])
        return ids

    # ------------------------------------------------------------------
    # POS: "create customer" with the mobile / CNIC of an existing person
    # ------------------------------------------------------------------
    @api.model
    def create_from_ui(self, partner):
        if not partner.get('id'):
            mobile = partner.get('mobile')
            country = partner.get('country_code_id')
            if isinstance(country, (list, tuple)):
                country = country[0] if country else None
            existing = self._find_person(mobile=mobile, country=int(country) if country else None,
                                         cnic=partner.get('cnic_no'))
            if existing:
                tags = self.env['res.partner.category']
                donor = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
                if donor:
                    tags |= donor
                existing._add_person_tags(tags)
                return existing.id
        return super().create_from_ui(partner)

    # ------------------------------------------------------------------
    @api.constrains('primary_registration_id', 'active')
    def _check_duplicate_registration_id(self):
        for rec in self.filtered(lambda p: p.active and p.primary_registration_id):
            other = self.with_context(active_test=True).search([
                ('id', '!=', rec.id), '|', ('primary_registration_id', '=', rec.primary_registration_id),
                ('registration_ids.code', '=', rec.primary_registration_id)], limit=1)
            if other:
                raise ValidationError(_(
                    'Registration ID %(code)s already belongs to "%(name)s": a person has one contact.',
                    code=rec.primary_registration_id, name=other.display_name))
