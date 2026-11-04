from odoo import api, fields, models

from .sadqa_jariya_masjid import SadqaJariyaMasjid
from .sadqa_jariya_madrasa import SadqaJariyaMadrasa
from .sadqa_jariya_construction import SadqaJariyaConstruction
from .sadqa_jariya_flood import SadqaJariyaFlood

# The imported portal form is shown in its category tab as fields of the application
# (<prefix>_<field>, related to the form record), not as a list to open
FORM_TABS = {
    'masjid': SadqaJariyaMasjid,
    'madrasa': SadqaJariyaMadrasa,
    'construction': SadqaJariyaConstruction,
    'flood': SadqaJariyaFlood,
}


def _form_tab_attrs():
    attrs = {'_inherit': 'sadqa.jariya', '__module__': __name__}
    for prefix, detail in FORM_TABS.items():
        attrs[f'{prefix}_id'] = fields.Many2one(detail._name, string=detail._description, compute='_compute_form_tab_ids')
        form_fields = set(detail._portal_form_fields.values())
        for name, field in vars(detail).items():
            if name in form_fields:
                attrs[f'{prefix}_{name}'] = type(field)(related=f'{prefix}_id.{name}', string=field.args.get('string'))

    @api.depends(*(f'{prefix}_ids' for prefix in FORM_TABS))
    def _compute_form_tab_ids(self):
        for rec in self:
            for prefix in FORM_TABS:
                rec[f'{prefix}_id'] = rec[f'{prefix}_ids'][:1]

    attrs['_compute_form_tab_ids'] = _compute_form_tab_ids
    return attrs


SadqaJariyaFormTabs = type('SadqaJariyaFormTabs', (models.Model,), _form_tab_attrs())
