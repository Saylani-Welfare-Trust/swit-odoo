import re

from odoo import fields, models

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

# signed URLs valid 15 minutes: downloaded on import, before the ACK; either user may leave one out
PHOTO_FIELDS = (
    ('applicationImage', 'Application Photo', 'image'),
    ('institutionImage', 'Institution Photo', 'image'),
    ('assemblyImage', 'Assembly Photo', 'image'),
    ('studentsStudyingImage', 'Students During Lessons', 'image'),
    ('mealtimeImage', 'Students at Mealtime', 'image'),
)

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

FORM_SECTIONS = (GENERAL_FIELDS, PHOTO_FIELDS, MASJID_FIELDS, MADRASA_FIELDS, CONSTRUCTION_FIELDS, FLOOD_FIELDS)

FIELD_TYPES = {'char': fields.Char, 'text': fields.Text, 'integer': fields.Integer, 'float': fields.Float, 'date': fields.Date,
               'image': fields.Image}


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
            # photos up to 10 MB on the portal, kept at most 1920px here
            extra = {'max_width': 1920, 'max_height': 1920} if field_type == 'image' else {}
            attrs[field_name(key)] = FIELD_TYPES[field_type](label, **extra)
    return attrs


SadqaJariyaForm = type('SadqaJariyaForm', (models.Model,), _form_attrs())
