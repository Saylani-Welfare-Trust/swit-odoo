from odoo import api, fields, models

from .sadqa_jariya_form import FIELD_TYPES, FORM_SECTIONS, field_name

# The imported portal forms are shown in their tabs as fields of the application
# (<prefix>_<field>, related to the form record), not as a list to open
FORM_TABS = {
    'donee_form': ('donee', 'Donee Form'),
    'officer_form': ('officer', 'Officer Form'),
}


def _search_form_tab(submission):
    """Applications by their form of ``submission`` (needed to recompute the
    tab fields when a form changes)."""
    def search(self, operator, value):
        Form = self.env['sadqa.jariya.form'].sudo()
        if operator in ('=', '!=') and not value:
            with_form = Form.search([('submission', '=', submission)]).application_id
            return [('id', 'not in' if operator == '=' else 'in', with_form.ids)]
        forms = Form.search([('submission', '=', submission), ('id', operator, value)])
        return [('id', 'in', forms.application_id.ids)]
    return search


def _form_tab_attrs():
    attrs = {'_inherit': 'sadqa.jariya', '__module__': __name__}
    for prefix, (submission, string) in FORM_TABS.items():
        attrs[f'_search_{prefix}_id'] = _search_form_tab(submission)
        attrs[f'{prefix}_id'] = fields.Many2one('sadqa.jariya.form', string=string, compute='_compute_form_tab_ids',
                                                search=f'_search_{prefix}_id')
        for section in FORM_SECTIONS:
            for key, label, field_type in section:
                attrs[f'{prefix}_{field_name(key)}'] = FIELD_TYPES[field_type](related=f'{prefix}_id.{field_name(key)}', string=f'{label} ({string})')

    @api.depends('form_ids.submission')
    def _compute_form_tab_ids(self):
        for rec in self:
            for prefix, (submission, _string) in FORM_TABS.items():
                rec[f'{prefix}_id'] = rec.form_ids.filtered(lambda f: f.submission == submission)[:1]

    attrs['_compute_form_tab_ids'] = _compute_form_tab_ids
    return attrs


SadqaJariyaFormTabs = type('SadqaJariyaFormTabs', (models.Model,), _form_tab_attrs())
