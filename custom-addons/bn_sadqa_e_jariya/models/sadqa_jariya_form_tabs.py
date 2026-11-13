from odoo import api, fields, models

from .sadqa_jariya_form import FIELD_TYPES, FORM_SECTIONS, field_name

# The imported portal forms are shown in their tabs as fields of the application
# (<prefix>_<field>, related to the form record), not as a list to open
FORM_TABS = {
    'donee_form': ('donee', 'Donee Form'),
    'officer_form': ('officer', 'Officer Form'),
}


def _form_tab_attrs():
    attrs = {'_inherit': 'sadqa.jariya', '__module__': __name__}
    for prefix, (_submission, string) in FORM_TABS.items():
        attrs[f'{prefix}_id'] = fields.Many2one('sadqa.jariya.form', string=string, compute='_compute_form_tab_ids')
        for section in FORM_SECTIONS:
            for key, label, field_type in section:
                attrs[f'{prefix}_{field_name(key)}'] = FIELD_TYPES[field_type](related=f'{prefix}_id.{field_name(key)}', string=label)

    @api.depends('form_ids.submission')
    def _compute_form_tab_ids(self):
        for rec in self:
            for prefix, (submission, _string) in FORM_TABS.items():
                rec[f'{prefix}_id'] = rec.form_ids.filtered(lambda f: f.submission == submission)[:1]

    attrs['_compute_form_tab_ids'] = _compute_form_tab_ids
    return attrs


SadqaJariyaFormTabs = type('SadqaJariyaFormTabs', (models.Model,), _form_tab_attrs())
