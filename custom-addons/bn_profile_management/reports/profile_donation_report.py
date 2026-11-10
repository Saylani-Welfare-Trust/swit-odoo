import ast
import logging
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.tools import format_amount, format_date, format_datetime
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

PROFILE_FORM = 'bn_profile_management.profile_management_view_form'
# Page of the profile form whose tabs are the donations
DONATION_PAGE = 'donation'
# Columns repeating the contact itself on every row
CONTACT_COLUMNS = ('donor_id', 'partner_id')
SKIPPED_TYPES = ('binary', 'image', 'one2many', 'html', 'properties', 'properties_definition', 'json')


class ProfileDonationReportData(models.AbstractModel):
    """Contact details and the Donation tabs of the profile form, for the PDF
    and the Excel report.

    Read from the profile form itself: the details are the fields the form
    shows for the contact (its visibility rules applied), and every Donation
    tab - whichever module adds it - is its list with the same columns. A new
    tab or column needs no change here."""
    _name = 'profile.donation.report.data'
    _description = 'Profile & donations report data'

    # ------------------------------------------------------------------
    # form layout
    # ------------------------------------------------------------------
    @api.model
    def _profile_form_arch(self, tag=None):
        """The profile form as dynamic profiling builds it: the fields every
        Profile Type may select, shown by the contact's tags, laid out in the
        order chosen on ``tag`` (as in that Profile Type's menu)."""
        view = self.env.ref(PROFILE_FORM)
        context = {'lang': self.env.lang}
        if tag:
            context['profile_tag_view_ref'] = tag.id
        arch, _view = self.env['res.partner'].sudo().with_context(**context)._get_view(
            view_id=view.id, view_type='form')
        return arch

    @api.model
    def _profile_tag(self, partner):
        """The contact's Profile Type whose form layout the report follows:
        the first of its tags that orders form fields, else its first
        Profile Type."""
        types = partner.sudo().category_id.filtered('is_profile_type')
        return types.filtered('profile_form_field_ids')[:1] or types[:1]

    def _allowed(self, node):
        groups = node.get('groups')
        return not groups or self.env.user.user_has_groups(groups)

    @api.model
    def _layout(self, tag=None):
        """(detail field nodes, donation tabs [(title, one2many field node,
        [page nodes it sits in])])."""
        arch = self._profile_form_arch(tag)
        sheet = arch.find('.//sheet')
        notebook = sheet.find('.//notebook')
        general = arch.find(".//page[@name='general_info']")
        donation = arch.find(".//page[@name='%s']" % DONATION_PAGE)
        details, tabs = [], []
        # the fields above the tabs and those of General Information
        for node in sheet.iter('field'):
            if self._ancestor_tag(node, ('tree', 'kanban', 'form'), stop=sheet):
                continue
            if self._inside(node, notebook) and not self._inside(node, general):
                continue
            details.append(node)
        if donation is not None:
            for page in donation.iter('page'):
                if page is donation or not self._allowed(page):
                    continue
                for node in page.iter('field'):
                    if node.find('tree') is not None:
                        pages = [p for p in node.iterancestors('page')]
                        tabs.append((page.get('string') or page.get('name'), node, pages))
                        break
        return details, tabs

    @staticmethod
    def _inside(node, container):
        if container is None:
            return False
        parent = node.getparent()
        while parent is not None:
            if parent is container:
                return True
            parent = parent.getparent()
        return False

    @staticmethod
    def _ancestor_tag(node, tags, stop):
        parent = node.getparent()
        while parent is not None and parent is not stop:
            if parent.tag in tags:
                return True
            parent = parent.getparent()
        return False

    # ------------------------------------------------------------------
    # values
    # ------------------------------------------------------------------
    def _visible(self, record, expression):
        """Evaluate an ``invisible`` attribute of the form on ``record``."""
        expression = (expression or '').strip()
        if not expression or expression in ('0', 'False'):
            return True
        if expression in ('1', 'True'):
            return False
        try:
            names = {n.id for n in ast.walk(ast.parse(expression, mode='eval')) if isinstance(n, ast.Name)}
        except SyntaxError:
            return True
        values = {'context': {}, 'uid': self.env.uid, 'True': True, 'False': False, 'None': None}
        for name in names - set(values):
            if name not in record._fields:
                return True
            field, value = record._fields[name], record[name]
            if field.type == 'many2one':
                value = value.id or False
            elif field.type in ('one2many', 'many2many'):
                value = value.ids
            values[name] = value
        try:
            return not safe_eval(expression, values)
        except Exception:  # noqa: BLE001 - shown when it cannot be decided
            return True

    def _value(self, record, fname):
        """(text for the PDF, value for Excel) of a field."""
        field = record._fields[fname]
        value = record[fname]
        if field.type == 'many2one':
            text = value.display_name or ''
            return text, text
        if field.type == 'many2many':
            text = ', '.join(value.mapped('display_name'))
            return text, text
        if field.type == 'selection':
            text = dict(field._description_selection(self.env)).get(value, '') if value else ''
            return text, text
        if field.type == 'boolean':
            text = _('Yes') if value else _('No')
            return text, text
        if field.type == 'date':
            return (format_date(self.env, value) if value else ''), (value or '')
        if field.type == 'datetime':
            if not value:
                return '', ''
            local = fields.Datetime.context_timestamp(record, value)
            return format_datetime(self.env, value), local.replace(tzinfo=None)
        if field.type == 'monetary':
            currency = record[field.get_currency_field(record)] if field.get_currency_field(record) else False
            currency = currency or self.env.company.currency_id
            return format_amount(self.env, value or 0.0, currency), value or 0.0
        if field.type == 'float':
            return '{:,.2f}'.format(value or 0.0), value or 0.0
        if field.type == 'integer':
            return '{:,}'.format(value or 0), value or 0
        text = '' if value in (False, None) else str(value)
        return text, text

    def _label(self, model, node):
        return node.get('string') or model._fields[node.get('name')]._description_string(self.env)

    # ------------------------------------------------------------------
    @api.model
    def _contact_data(self, partner):
        """{'partner', 'details': [(label, text, value)], 'tabs': [tab]} where a
        tab is {'title', 'columns': [label], 'numeric': [bool], 'rows':
        [[(text, value)]], 'totals': [text or '']} - tabs without records left out."""
        details_nodes, tab_nodes = self._layout(self._profile_tag(partner))
        seen, details = set(), []
        for node in details_nodes:
            fname = node.get('name')
            field = partner._fields.get(fname)
            if (not field or fname in seen or field.type in SKIPPED_TYPES or not self._allowed(node)
                    or field.groups and not self.env.user.user_has_groups(field.groups)
                    or not self._visible(partner, node.get('invisible'))):
                continue
            seen.add(fname)
            text, value = self._value(partner, fname)
            if text in ('', False) or (field.type in ('boolean', 'integer', 'float', 'monetary') and not partner[fname]):
                continue
            details.append((self._label(partner, node), text, value))
        tabs = []
        for title, node, pages in tab_nodes:
            # the Donation page (and the tab) as the contact's Profile Types show them
            if not all(self._visible(partner, page.get('invisible')) for page in pages):
                continue
            fname = node.get('name')
            field = partner._fields.get(fname)
            if not field or field.type not in ('one2many', 'many2many'):
                continue
            Model = self.env[field.comodel_name]
            if not Model.check_access_rights('read', raise_exception=False):
                continue
            records = partner[fname]
            if not records:
                continue
            tree = node.find('tree')
            columns = []
            for col in tree.iter('field'):
                cname = col.get('name')
                cfield = Model._fields.get(cname)
                if (not cfield or cfield.type in SKIPPED_TYPES or cname in CONTACT_COLUMNS
                        or col.get('column_invisible') in ('1', 'True') or col.get('invisible') in ('1', 'True')
                        or not self._allowed(col) or cfield.groups and not self.env.user.user_has_groups(cfield.groups)):
                    continue
                columns.append((cname, self._label(Model, col), cfield.type in ('monetary', 'float', 'integer'),
                                bool(col.get('sum')) or cfield.type == 'monetary'))
            rows, totals = [], [0.0] * len(columns)
            for record in records:
                row = []
                for i, (cname, _label, numeric, summed) in enumerate(columns):
                    text, value = self._value(record, cname)
                    row.append((text, value))
                    if summed:
                        totals[i] += value or 0.0
                rows.append(row)
            total_texts = []
            for i, (cname, _label, numeric, summed) in enumerate(columns):
                if not summed:
                    total_texts.append('')
                elif Model._fields[cname].type == 'monetary':
                    total_texts.append(format_amount(self.env, totals[i], self.env.company.currency_id))
                else:
                    total_texts.append('{:,.2f}'.format(totals[i]))
            tabs.append({
                'title': title,
                'columns': [c[1] for c in columns],
                'numeric': [c[2] for c in columns],
                'rows': rows,
                'totals': total_texts if any(c[3] for c in columns) else [],
                # the first amount column, for the summary on the first page
                'summary_total': next((t for t in total_texts if t), ''),
                'total_values': [totals[i] if c[3] else None for i, c in enumerate(columns)],
            })
        return {'partner': partner, 'details': details, 'tabs': tabs}

    @api.model
    def _report_data(self, partners):
        return [self._contact_data(partner) for partner in partners]


class ProfileDonationReport(models.AbstractModel):
    _name = 'report.bn_profile_management.profile_donation_report'
    _description = 'Profile & Donations (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        partners = self.env['res.partner'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'res.partner',
            'docs': partners,
            'contacts': self.env['profile.donation.report.data']._report_data(partners),
            'printed_on': format_datetime(self.env, fields.Datetime.now()),
        }


class ProfileDonationReportXlsx(models.AbstractModel):
    _name = 'report.bn_profile_management.profile_donation_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Profile & Donations (Excel)'

    def generate_xlsx_report(self, workbook, data, partners):
        contacts = self.env['profile.donation.report.data']._report_data(partners)
        title = workbook.add_format({'bold': True, 'font_size': 14})
        head = workbook.add_format({'bold': True, 'bg_color': '#3b3591', 'font_color': '#ffffff', 'border': 1,
                                    'text_wrap': True, 'valign': 'vcenter'})
        label = workbook.add_format({'bold': True, 'bg_color': '#ecebf6', 'border': 1})
        cell = workbook.add_format({'border': 1, 'valign': 'top'})
        number = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        date_fmt = workbook.add_format({'border': 1, 'num_format': 'dd-mm-yyyy'})
        datetime_fmt = workbook.add_format({'border': 1, 'num_format': 'dd-mm-yyyy hh:mm'})
        total = workbook.add_format({'bold': True, 'border': 1, 'top': 2, 'num_format': '#,##0.00'})

        def put(sheet, row, col, value):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                sheet.write_number(row, col, value, number)
            elif isinstance(value, datetime):
                sheet.write_datetime(row, col, value, datetime_fmt)
            elif isinstance(value, date):
                sheet.write_datetime(row, col, fields.Datetime.to_datetime(value), date_fmt)
            else:
                sheet.write(row, col, value or '', cell)

        # 1. the contacts: one block of details each
        sheet = workbook.add_worksheet(_('Contacts'))
        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 60)
        row = 0
        for contact in contacts:
            sheet.write(row, 0, contact['partner'].display_name, title)
            row += 1
            for lbl, _text, value in contact['details']:
                sheet.write(row, 0, lbl, label)
                put(sheet, row, 1, value)
                row += 1
            for tab in contact['tabs']:
                sheet.write(row, 0, tab['title'], label)
                sheet.write(row, 1, _('%s record(s)') % len(tab['rows']), cell)
                row += 1
            row += 1

        # 2. one sheet per donation tab, with every selected contact's records
        sheets = {}
        for contact in contacts:
            for tab in contact['tabs']:
                key = (tab['title'], tuple(tab['columns']))
                if key not in sheets:
                    name = self._sheet_name(tab['title'], {s['sheet'].name for s in sheets.values()})
                    ws = workbook.add_worksheet(name)
                    ws.write_row(0, 0, [_('Contact')] + tab['columns'], head)
                    ws.set_column(0, len(tab['columns']), 20)
                    ws.freeze_panes(1, 1)
                    sheets[key] = {'sheet': ws, 'row': 1}
                entry = sheets[key]
                ws = entry['sheet']
                for values in tab['rows']:
                    ws.write(entry['row'], 0, contact['partner'].display_name, cell)
                    for col, (_text, value) in enumerate(values, start=1):
                        put(ws, entry['row'], col, value)
                    entry['row'] += 1
                if tab['totals']:
                    ws.write(entry['row'], 0, _('Total: %s', contact['partner'].display_name), total)
                    for col, value in enumerate(tab['total_values'], start=1):
                        if value is not None:
                            ws.write_number(entry['row'], col, value, total)
                    entry['row'] += 2

    @staticmethod
    def _sheet_name(title, used):
        name = ''.join(ch for ch in title if ch not in '[]:*?/\\')[:31] or 'Sheet'
        base, n = name, 2
        while name in used:
            suffix = ' (%d)' % n
            name = base[:31 - len(suffix)] + suffix
            n += 1
        return name
