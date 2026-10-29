# -*- coding: utf-8 -*-

from collections import defaultdict

from markupsafe import Markup

from odoo import models, api, _
from odoo.tools.misc import formatLang


class LineChangeLogMixin(models.AbstractModel):
    """Post every line added to, changed on or deleted from a document in that
    document's chatter (Material Request, Purchase Request, RFQ / Purchase
    Order). A line model using it names its document field (_line_log_parent)
    and the fields worth logging (_line_log_fields). Lines created together
    with their document are not logged: they are part of how it was created."""
    _name = 'line.change.log.mixin'
    _description = 'Line Change Log'

    _line_log_parent = None
    _line_log_fields = []

    def _line_log_skip(self):
        """Section and note lines are layout, not lines worth logging."""
        return 'display_type' in self._fields and bool(self.display_type)

    def _line_log_ignored(self, field_name):
        """Whether a change of ``field_name`` on this line is already logged
        some other way."""
        return False

    def _line_log_format(self, field_name, value):
        field = self._fields[field_name]
        if field.type in ('float', 'monetary'):
            digits = field.get_digits(self.env) if field.type == 'float' else None
            return formatLang(self.env, value, digits=digits[1] if digits else 2)
        if field.type in ('many2many', 'one2many'):
            return ', '.join(value.mapped('display_name')) or '-'
        return field.convert_to_display_name(value, self) or '-'

    def _line_log_item(self, action, parts):
        label = self.product_id.display_name if 'product_id' in self._fields and self.product_id \
            else self.display_name
        return Markup('<li><b>%s</b> %s%s</li>') % (
            action, label, Markup(' &#8212; ') + ', '.join(parts) if parts else '')

    def _line_log_summary(self):
        """The line's logged values, for a line added or deleted. The product
        and the descriptions are left out: the product already names the line."""
        return [
            '%s %s' % (self._fields[name]._description_string(self.env), self._line_log_format(name, self[name]))
            for name in self._line_log_fields
            if name != 'product_id' and name in self._fields and self[name]
            and self._fields[name].type not in ('char', 'text', 'html')
        ]

    def _line_log_post(self, items_by_parent):
        for parent, items in items_by_parent.items():
            # sudo: whoever may edit the lines need not be allowed to post on the document.
            parent.sudo().message_post(
                body=Markup('%s<ul>%s</ul>') % (_('Lines updated'), Markup().join(items)),
                subtype_xmlid='mail.mt_note')

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        items = defaultdict(list)
        for line in lines:
            parent = line[line._line_log_parent]
            # Created in the same transaction as its document (same create_date).
            if not parent or parent.create_date == line.create_date or line._line_log_skip():
                continue
            items[parent].append(line._line_log_item(_('Added:'), line._line_log_summary()))
        lines._line_log_post(items)
        return lines

    def write(self, vals):
        names = [name for name in self._line_log_fields if name in vals and name in self._fields]
        before = {line: {name: line[name] for name in names} for line in self} if names else {}
        res = super().write(vals)
        items = defaultdict(list)
        for line, old_values in before.items():
            if line._line_log_skip():
                continue
            parts = [
                '%s %s → %s' % (self._fields[name]._description_string(self.env),
                                 line._line_log_format(name, old_values[name]),
                                 line._line_log_format(name, line[name]))
                for name in names
                if old_values[name] != line[name] and not line._line_log_ignored(name)
            ]
            if parts:
                items[line[line._line_log_parent]].append(line._line_log_item(_('Changed:'), parts))
        self._line_log_post(items)
        return res

    def unlink(self):
        items = defaultdict(list)
        for line in self:
            parent = line[line._line_log_parent]
            if parent and not line._line_log_skip():
                items[parent].append(line._line_log_item(_('Deleted:'), line._line_log_summary()))
        self._line_log_post(items)
        return super().unlink()
