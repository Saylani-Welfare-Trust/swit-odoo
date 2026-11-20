import re

from odoo import api, fields, models

# Institutional form field reference of the portal contract: (key, English label, type) per section.
# The portal sends one flat camelCase form; its keys are stored on snake_case fields (accountTitle -> account_title).
GENERAL_FIELDS = (
    ('requestDate', 'Request Date', 'date'),
    ('institutionName', 'Madrasa / Masjid Name', 'char'),
    ('institutionAddress', 'Full Address', 'text'),
    ('responsiblePersonName', 'Administrator / Imam / Trustee Name', 'char'),
    ('contactNumber', 'Contact Number', 'char'),
    ('whatsappNumber', 'WhatsApp Number', 'char'),
    ('registeredTrust', 'Registered Trust', 'char'),
    ('orgAffiliation', 'Organization Affiliation', 'char'),
    ('establishedYear', 'Established', 'char'),
    ('teachingRooms', 'Teaching Rooms', 'integer'),
    ('residentialRooms', 'Residential Rooms', 'integer'),
    ('totalArea', 'Total Madrasa / Masjid Area', 'char'),
    # entered by the donee and by the officer on the portal, never sent by Odoo
    ('accountTitle', 'Account Title', 'char'),
    ('accountNumber', 'Account Number', 'char'),
    ('cnicNumber', 'CNIC Number', 'char'),
    ('monthlyExpense', 'Total Monthly Expenses', 'float'),
    ('expSalaries', 'Salary Expenses', 'float'),
    ('expRation', 'Ration Expenses', 'float'),
    ('expUtilityBills', 'Gas / Electricity Bills', 'float'),
    ('emergencyContactIfNoSupport', 'Contacted If No Support In A Month', 'text'),
    ('currentSaylaniSupport', 'Current Saylani Support', 'float'),
    ('supportConstruction', 'Construction Support', 'char'),
    ('supportMeat', 'Meat Support', 'char'),
    ('supportCookedFood', 'Cooked Food Support', 'char'),
    ('studentStandard', 'Student Standard', 'char'),
    ('cleanlinessEnv', 'Cleanliness', 'char'),
    ('committeeMembers', 'Number of Committee Members', 'integer'),
    ('monthlyMeetings', 'Number of Monthly Meetings', 'integer'),
)

# Photos (signed URLs valid 15 minutes, either user may leave one out): downloaded on import, before the ACK,
# into the application's Documents, where they can be viewed, removed and added to. key -> (document type, label)
PHOTO_DOCUMENT_TYPES = {
    'applicationImage': ('application_photo', 'Application Photo'),
    'institutionImage': ('institution_photo', 'Institution Photo'),
    'assemblyImage': ('assembly_photo', 'Assembly Photo'),
    'studentsStudyingImage': ('students_studying_photo', 'Students During Lessons'),
    'mealtimeImage': ('mealtime_photo', 'Students at Mealtime'),
}

MASJID_FIELDS = (
    ('worshippersFajr', 'Fajr Worshippers', 'integer'),
    ('worshippersDhuhr', 'Dhuhr Worshippers', 'integer'),
    ('worshippersAsr', 'Asr Worshippers', 'integer'),
    ('worshippersMaghrib', 'Maghrib Worshippers', 'integer'),
    ('worshippersIsha', 'Isha Worshippers', 'integer'),
    ('worshippersJumuah', 'Jumuah Worshippers', 'integer'),
    ('darsSchedule', 'Dars Schedule', 'char'),
    ('bookName', 'Book Name', 'char'),
    ('participantsCount', 'Number of Participants', 'integer'),
    ('imamOtherEngagements', "Imam's Other Engagements", 'text'),
    ('otherIncomeSources', 'Government / Other Sources of Income', 'text'),
    ('monthlyMasjidSupport', 'Monthly Support from the Masjid', 'float'),
)

_LEVELS = (('Aidadiyah', 'Aidadiyah'), ('Aamah1', 'Aamah, Year 1'), ('Aamah2', 'Aamah, Year 2'),
           ('Khassah1', 'Khassah, Year 1'), ('Khassah2', 'Khassah, Year 2'), ('Aaliyah1', 'Aaliyah, Year 1'),
           ('Aaliyah2', 'Aaliyah, Year 2'), ('Almiyah1', 'Almiyah, Year 1'), ('Almiyah2', 'Almiyah, Year 2'),
           ('Takhasus1', 'Takhasus, Year 1'), ('Takhasus2', 'Takhasus, Year 2'))

MADRASA_FIELDS = tuple(
    (f'{gender}{level}', f'{label} - {level_label}', 'integer')
    for gender, label in (('male', 'Male Students'), ('female', 'Female Students'))
    for level, level_label in _LEVELS
) + (
    ('totalDarsNizami', 'Total Dars-e-Nizami Students', 'integer'),
    ('resDarsNizami', 'Residential Dars-e-Nizami Students', 'integer'),
    ('nonResDarsNizami', 'Non-residential Dars-e-Nizami Students', 'integer'),
    ('hifzStudents', 'Hifz Students', 'integer'),
    ('nazraStudents', 'Nazra Students', 'integer'),
    ('tajweedStudents', 'Tajweed Students', 'integer'),
    ('schoolStudents', 'School Students', 'integer'),
    ('otherCourses', 'Other Courses', 'integer'),
    ('totalResidential', 'Total Residential Students', 'integer'),
    ('totalNonResidential', 'Total Non-residential Students', 'integer'),
    ('totalMadrasaStudents', 'Total Madrasa Students (Male and Female)', 'integer'),
    ('staffDarsNizami', 'Dars-e-Nizami Staff', 'integer'),
    ('staffHifzNazra', 'Hifz and Nazra Staff', 'integer'),
    ('staffNonTeaching', 'Non-teaching Staff', 'integer'),
    ('totalStaff', 'Total Staff', 'integer'),
    ('currTestPercentage', 'Current Test Percentage', 'char'),
    ('orgStudentsCount', 'Students Affiliated with the Organization', 'integer'),
    ('orgStudentExamPercentage', 'Exam Percentage of Affiliated Students', 'char'),
)

# construction, and flood-institute after its three flood fields
CONSTRUCTION_FIELDS = (
    ('totalEstimate', 'Total Estimated Cost', 'float'),
    ('costIronSteel', 'Steel / Rebar Cost', 'float'),
    ('costCement', 'Cement Cost', 'float'),
    ('costLabor', 'Labour Cost', 'float'),
    ('currentWork', 'Current Work', 'text'),
    ('remainingWork', 'Remaining Work', 'text'),
)

FLOOD_FIELDS = (
    ('shortIntro', 'Brief Description of the Situation', 'text'),
    ('statusBeforeFlood', 'Institution Before the Flood', 'text'),
    ('statusAfterFlood', 'Institution After the Flood', 'text'),
)

FORM_SECTIONS = (GENERAL_FIELDS, MASJID_FIELDS, MADRASA_FIELDS, CONSTRUCTION_FIELDS, FLOOD_FIELDS)

FIELD_TYPES = {'char': fields.Char, 'text': fields.Text, 'integer': fields.Integer, 'float': fields.Float, 'date': fields.Date}


def field_name(key):
    """snake_case field of a portal form key: maleAamah1 -> male_aamah1"""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', key).lower()


def _form_attrs():
    attrs = {
        '_name': 'sadqa.jariya.form',
        '_description': 'Sadqa e Jariya Portal Form',
        '_order': 'submission',
        '__module__': __name__,
        '__doc__': "A completed portal form: the donee's (getSubmittedForms form) or an officer's own (getCompletedInquiries inquiry.form)",
        'application_id': fields.Many2one('sadqa.jariya', string='Application', required=True, ondelete='cascade'),
        'submission': fields.Selection([('donee', 'Donee'), ('officer', 'Inquiry Officer')], string='Submitted By', required=True),
        'institution_type': fields.Selection([('masjid', 'Masjid'), ('madrasa', 'Madrasa')], string='Institution Type'),
        # the row's formKind: construction / flood-institute forms (legacy rows) carry those sections
        'form_kind': fields.Char('Portal Form Kind'),
        'submitted_at': fields.Datetime('Submitted At'),
        # officer forms: one per portal report (a reopened inquiry is a new report)
        'report_id': fields.Many2one('sadqa.jariya.inquiry.report', string='Inquiry Report', ondelete='cascade'),
        '_sql_constraints': [
            ('report_unique', 'unique(report_id)', 'An inquiry report has one officer form.'),
        ],
        # portal key -> field
        '_portal_form_fields': {key: field_name(key) for section in FORM_SECTIONS for key, _label, _type in section},
    }
    for section in FORM_SECTIONS:
        for key, label, field_type in section:
            attrs[field_name(key)] = FIELD_TYPES[field_type](label)

    # photos imported onto the form before they went to the Documents: moved there on upgrade
    for key, (_document_type, label) in PHOTO_DOCUMENT_TYPES.items():
        attrs[field_name(key)] = fields.Image(f'{label} (moved to Documents)')

    def _move_photos_to_documents(self):
        """Runs on install / upgrade (data/move_portal_photos.xml); nothing is left to move after the first time"""
        Document = self.env['sadqa.jariya.document']
        for key, (document_type, _label) in PHOTO_DOCUMENT_TYPES.items():
            name = field_name(key)
            for form in self.search([(name, '!=', False)]):
                Document.create({
                    'application_id': form.application_id.id,
                    'document_type': document_type,
                    'image_data': form[name],
                    'image_filename': f'{document_type}.jpg',
                    'uploaded_from': form.submission,
                    'form_id': form.id,
                })
                form[name] = False

    attrs['_move_photos_to_documents'] = api.model(_move_photos_to_documents)
    return attrs


SadqaJariyaForm = type('SadqaJariyaForm', (models.Model,), _form_attrs())
