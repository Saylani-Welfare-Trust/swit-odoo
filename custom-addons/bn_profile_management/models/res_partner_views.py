# -*- coding: utf-8 -*-
"""Profile Management views built from the Profile Type (tag) configuration.

* List / search: the menu of a profile tag passes ``profile_tag_view_ref`` (the
  tag id) in its context. The name must end in ``_view_ref``: the web client
  drops every other context key before asking the server for views. The list gets one column, and the search view one field, per
  field selected on that tag (in the order of CURATED_PROFILE_FIELDS).
* Form: every selectable field has a slot, shown only when one of the
  contact's tags selects it (``profile_visible_form_field_names``).

The view cache key includes the tag and its selected fields, so editing a
tag rebuilds the views.
"""
from lxml import etree

from odoo import api, models

from .res_partner_category import CURATED_PROFILE_FIELDS

PROFILE_VIEWS = {
    'tree': 'bn_profile_management.profile_management_view_tree',
    'search': 'bn_profile_management.profile_management_view_search',
    'form': 'bn_profile_management.profile_management_view_form',
}
# Always on the form: needed to identify and register a profile.
FORM_ALWAYS_VISIBLE = {'name', 'category_id', 'mobile', 'country_code_id'}
# Always in the list / search, whatever the tag selects.
LIST_FIXED = {'complete_name', 'state'}
SEARCH_FIXED = {'complete_name', 'registration_ids', 'category_id'}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _profile_view_tag(self):
        tag_id = self.env.context.get('profile_tag_view_ref')
        if not tag_id:
            return self.env['res.partner.category']
        return self.env['res.partner.category'].sudo().browse(tag_id).exists()

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        tag = self._profile_view_tag()
        if tag:
            # The selected fields and their positions (not write_date, which
            # does not change between two edits of the same transaction).
            lines = self.env['profile.view.field'].sudo().search([('category_id', '=', tag.id)])
            key += ('profile_tag', tag.id, tuple((l.view_type, l.field_id.id, l.sequence) for l in lines))
        return key

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        profile_view = self.env.ref(PROFILE_VIEWS.get(view_type, ''), raise_if_not_found=False) \
            if view_type in PROFILE_VIEWS else None
        if not profile_view or view != profile_view:
            return arch, view
        tag = self._profile_view_tag()
        if view_type == 'form':
            self._profile_build_form(arch)
            if tag:
                self._profile_order_form(arch, tag)
            return arch, view
        if tag:
            if view_type == 'tree':
                self._profile_build_list(arch, tag)
            else:
                self._profile_build_search(arch, tag)
        return arch, view

    # ------------------------------------------------------------------
    def _profile_selected(self, tag, view_type):
        """Field names selected on ``tag`` for ``view_type``, in the order
        chosen by the administrator."""
        names = tag._profile_view_lines(view_type).mapped('field_id.name')
        return [name for name in names if name in self._fields]

    def _profile_build_list(self, arch, tag):
        """Columns = the tag's List View Fields, then the status."""
        for node in arch.xpath('//tree/field'):
            if node.get('name') not in LIST_FIXED:
                node.getparent().remove(node)
        state = arch.xpath('//tree/field[@name="state"]')
        anchor = state[0] if state else None
        for name in self._profile_selected(tag, 'list'):
            field = self._fields[name]
            node = etree.Element('field', name=name, optional='show')
            if field.type == 'many2many':
                node.set('widget', 'many2many_tags')
            elif field.type == 'binary':
                node.set('widget', 'image' if name.startswith('image') else 'binary')
            if anchor is not None:
                anchor.addprevious(node)
            else:
                arch.xpath('//tree')[0].append(node)

    def _profile_build_search(self, arch, tag):
        """Search fields = the tag's Search View Fields (searchable ones)."""
        search = arch.xpath('//search')[0]
        for node in search.xpath('./field'):
            if node.get('name') not in SEARCH_FIXED:
                search.remove(node)
        anchor = search.xpath('./field[@name="category_id"]')
        for name in self._profile_selected(tag, 'search'):
            field = self._fields[name]
            if field.type in ('binary', 'one2many') or not (field.store or field.search):
                continue
            node = etree.Element('field', name=name)
            if anchor:
                anchor[0].addprevious(node)
            else:
                search.insert(0, node)

    def _profile_build_form(self, arch):
        """Every selectable field shows only when one of the contact's tags
        selects it; fields the form did not have go to "Other Details"."""
        condition = "',%s,' not in profile_visible_form_field_names"
        present = set()
        for node in arch.xpath('//sheet//field[@name]'):
            name = node.get('name')
            if name not in CURATED_PROFILE_FIELDS or node.xpath('ancestor::field'):
                continue
            present.add(name)
            if name in FORM_ALWAYS_VISIBLE or 'profile_visible_form_field_names' in (node.get('invisible') or ''):
                continue
            current = node.get('invisible')
            visible_rule = condition % name
            node.set('invisible', '(%s) or %s' % (current, visible_rule) if current else visible_rule)
        missing = [name for name in CURATED_PROFILE_FIELDS if name not in present and name in self._fields]
        page = arch.xpath('//page[@name="general_info"]')
        if not missing or not page:
            return
        group = etree.SubElement(page[0], 'group', name='profile_other_details', string='Other Details')
        for name in missing:
            node = etree.SubElement(group, 'field', name=name, invisible=condition % name)
            if self._fields[name].type == 'many2many':
                node.set('widget', 'many2many_tags')

    def _profile_order_form(self, arch, tag):
        """Lay out the General Information page in the order chosen on the
        menu's tag: its form fields first, in that order, then the others.
        The field nodes are moved as they are, keeping all their rules
        (required, read-only, file name ...). The header (name, photo,
        address, mobile, email, tags) keeps its place."""
        page = arch.xpath('//page[@name="general_info"]')
        if not page:
            return
        page = page[0]
        nodes = [node for node in page.xpath('.//field[@name]') if not node.xpath('ancestor::field')]
        by_name = {node.get('name'): node for node in nodes}
        chosen = [name for name in self._profile_selected(tag, 'form') if name in by_name]
        ordered = [by_name[name] for name in chosen] + [n for n in nodes if n.get('name') not in chosen]
        for node in nodes:
            node.getparent().remove(node)
        for child in list(page):
            page.remove(child)
        grid = etree.SubElement(page, 'group', name='general_info_ordered')
        columns = (etree.SubElement(grid, 'group', name='general_info_col_1'),
                   etree.SubElement(grid, 'group', name='general_info_col_2'))
        visible = [n for n in ordered if n.get('name') in chosen]
        others = [n for n in ordered if n.get('name') not in chosen]
        # Positions run down the left column, then down the right column.
        half = (len(visible) + 1) // 2
        for index, node in enumerate(visible):
            columns[0 if index < half else 1].append(node)
        for node in others:
            columns[1].append(node)
