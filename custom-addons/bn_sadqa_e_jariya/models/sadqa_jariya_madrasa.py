from odoo import models, fields


class SadqaJariyaMadrasa(models.Model):
    _name = 'sadqa.jariya.madrasa'
    _description = 'Madrasa Application Details'

    application_id = fields.Many2one('sadqa.jariya', string='Application', required=True, ondelete='cascade')

    # Madaris Checking Form (چیکنگ فارم برائے مدارس)
    # Administrative
    md_number = fields.Char(string='MD Number')
    new_code_serial = fields.Char(string='New Code / Serial No.')
    case_number = fields.Char(string='Case Number')
    request_date = fields.Date(string='Request Date')

    # Basic Information
    madarsa_name = fields.Char(string='Madrasa Name')
    address = fields.Text(string='Address')
    mohtamim_name = fields.Char(string='Mohtamim Name')
    contact_number = fields.Char(string='Contact Number')
    whatsapp_number = fields.Char(string='WhatsApp Number')

    # Registry & Infrastructure
    registered_trust = fields.Char(string='Registered Trust')
    tanzeem_ilhaaq = fields.Char(string='Tanzeem Ilhaaq')
    established_since = fields.Char(string='Established Since')
    teaching_rooms = fields.Integer(string='Teaching Rooms')
    residential_rooms = fields.Integer(string='Residential Rooms')
    area_of_madarsa = fields.Char(string='Area of Madrasa')
    account_number = fields.Char(string='Account Number')
    account_cnic = fields.Char(string='Account CNIC')

    # Monthly Expenses (ماہانہ خرچ)
    monthly_expense = fields.Float(string='Monthly Expense')
    exp_salaries = fields.Float(string='Salaries')
    exp_ration = fields.Float(string='Ration')
    exp_utility_bills = fields.Float(string='Gas / Electricity Bills')
    emergency_contact_if_no_support = fields.Char(string='Contacted If No Support Came')

    # Previous Saylani Support (سیلانی کا سابقہ تعاون)
    amount_received_from_saylani = fields.Float(string='Amount Received from Saylani')
    support_construction = fields.Char(string='Construction Support')
    support_meat = fields.Char(string='Meat Support')
    support_cooked_food = fields.Char(string='Cooked Food Support')

    # Environmental Assessment
    committee_members = fields.Integer(string='Committee Members')
    monthly_meetings = fields.Integer(string='Monthly Meetings')

    # Male students (طلبہ)
    male_aidadiyah = fields.Integer(string='Aidadiyah (Male)')
    male_aamah_1 = fields.Integer(string='Aamah 1 (Male)')
    male_aamah_2 = fields.Integer(string='Aamah 2 (Male)')
    male_khassah_1 = fields.Integer(string='Khassah 1 (Male)')
    male_khassah_2 = fields.Integer(string='Khassah 2 (Male)')
    male_aaliyah_1 = fields.Integer(string='Aaliyah 1 (Male)')
    male_aaliyah_2 = fields.Integer(string='Aaliyah 2 (Male)')
    male_almiyah_1 = fields.Integer(string='Almiyah 1 (Male)')
    male_almiyah_2 = fields.Integer(string='Almiyah 2 (Male)')
    male_takhasus_1 = fields.Integer(string='Takhasus 1 (Male)')
    male_takhasus_2 = fields.Integer(string='Takhasus 2 (Male)')

    # Female students (طالبات)
    female_aidadiyah = fields.Integer(string='Aidadiyah (Female)')
    female_aamah_1 = fields.Integer(string='Aamah 1 (Female)')
    female_aamah_2 = fields.Integer(string='Aamah 2 (Female)')
    female_khassah_1 = fields.Integer(string='Khassah 1 (Female)')
    female_khassah_2 = fields.Integer(string='Khassah 2 (Female)')
    female_aaliyah_1 = fields.Integer(string='Aaliyah 1 (Female)')
    female_aaliyah_2 = fields.Integer(string='Aaliyah 2 (Female)')
    female_almiyah_1 = fields.Integer(string='Almiyah 1 (Female)')
    female_almiyah_2 = fields.Integer(string='Almiyah 2 (Female)')
    female_takhasus_1 = fields.Integer(string='Takhasus 1 (Female)')
    female_takhasus_2 = fields.Integer(string='Takhasus 2 (Female)')

    # Academic Departments & Totals
    total_dars_nizami = fields.Integer(string='Dars-e-Nizami Students')
    res_dars_nizami = fields.Integer(string='Dars-e-Nizami Residential')
    non_res_dars_nizami = fields.Integer(string='Dars-e-Nizami Non-Residential')
    hifz_students = fields.Integer(string='Hifz Students')
    nazra_students = fields.Integer(string='Nazra Students')
    tajweed_students = fields.Integer(string='Tajweed Students')
    school_students = fields.Integer(string='School Students')
    other_courses = fields.Integer(string='Other Courses')
    resident_students = fields.Integer(string='Resident Students')
    non_resident_students = fields.Integer(string='Non-Resident Students')
    total_madrasa_students = fields.Integer(string='Total Madrasa Students')

    # Attendance & Staffing
    staff_dars_nizami = fields.Integer(string='Dars-e-Nizami Staff')
    staff_hifz_nazra = fields.Integer(string='Hifz / Nazra Staff')
    total_non_teaching_staff = fields.Integer(string='Total Non-Teaching Staff')
    total_staff = fields.Integer(string='Total Staff')

    # Performance Metrics
    prev_test_percentage = fields.Char(string='Previous Test %')
    curr_test_percentage = fields.Char(string='Current Test %')
    org_students_count = fields.Integer(string='Organization Students')
    org_student_exam_percentage = fields.Char(string='Organization Students Exam %')

    # Reports & Remarks (officer observations come with the inquiry, decisions stay in Odoo)
    construction_explanation = fields.Text(string='Construction Explanation')

    # Madrasa form key in the portal export (institutional contract) -> field
    _portal_form_fields = {
        'mdNumber': 'md_number',
        'newCodeSerial': 'new_code_serial',
        'caseNumber': 'case_number',
        'requestDate': 'request_date',
        'jamiaName': 'madarsa_name',
        'fullAddress': 'address',
        'mohtamimName': 'mohtamim_name',
        'contactNumber': 'contact_number',
        'whatsappNumber': 'whatsapp_number',
        'registeredTrust': 'registered_trust',
        'orgAffiliation': 'tanzeem_ilhaaq',
        'establishedYear': 'established_since',
        'teachingRooms': 'teaching_rooms',
        'residentialRooms': 'residential_rooms',
        'totalArea': 'area_of_madarsa',
        'accountNumber': 'account_number',
        'cnicNumber': 'account_cnic',
        'monthlyExpense': 'monthly_expense',
        'expSalaries': 'exp_salaries',
        'expRation': 'exp_ration',
        'expUtilityBills': 'exp_utility_bills',
        'emergencyContactIfNoSupport': 'emergency_contact_if_no_support',
        'prevSaylaniSupport': 'amount_received_from_saylani',
        'supportConstruction': 'support_construction',
        'supportMeat': 'support_meat',
        'supportCookedFood': 'support_cooked_food',
        'committeeMembers': 'committee_members',
        'monthlyMeetings': 'monthly_meetings',
        'totalDarsNizami': 'total_dars_nizami',
        'resDarsNizami': 'res_dars_nizami',
        'nonResDarsNizami': 'non_res_dars_nizami',
        'hifzStudents': 'hifz_students',
        'nazraStudents': 'nazra_students',
        'tajweedStudents': 'tajweed_students',
        'schoolStudents': 'school_students',
        'otherCourses': 'other_courses',
        'totalResidential': 'resident_students',
        'totalNonResidential': 'non_resident_students',
        'totalMadrasaStudents': 'total_madrasa_students',
        'staffDarsNizami': 'staff_dars_nizami',
        'staffHifzNazra': 'staff_hifz_nazra',
        'staffNonTeaching': 'total_non_teaching_staff',
        'totalStaff': 'total_staff',
        'prevTestPercentage': 'prev_test_percentage',
        'currTestPercentage': 'curr_test_percentage',
        'orgStudentsCount': 'org_students_count',
        'orgStudentExamPercentage': 'org_student_exam_percentage',
        'constructionExplanation': 'construction_explanation',
        'maleAidadiyah': 'male_aidadiyah',
        'maleAamah1': 'male_aamah_1',
        'maleAamah2': 'male_aamah_2',
        'maleKhassah1': 'male_khassah_1',
        'maleKhassah2': 'male_khassah_2',
        'maleAaliyah1': 'male_aaliyah_1',
        'maleAaliyah2': 'male_aaliyah_2',
        'maleAlmiyah1': 'male_almiyah_1',
        'maleAlmiyah2': 'male_almiyah_2',
        'maleTakhasus1': 'male_takhasus_1',
        'maleTakhasus2': 'male_takhasus_2',
        'femaleAidadiyah': 'female_aidadiyah',
        'femaleAamah1': 'female_aamah_1',
        'femaleAamah2': 'female_aamah_2',
        'femaleKhassah1': 'female_khassah_1',
        'femaleKhassah2': 'female_khassah_2',
        'femaleAaliyah1': 'female_aaliyah_1',
        'femaleAaliyah2': 'female_aaliyah_2',
        'femaleAlmiyah1': 'female_almiyah_1',
        'femaleAlmiyah2': 'female_almiyah_2',
        'femaleTakhasus1': 'female_takhasus_1',
        'femaleTakhasus2': 'female_takhasus_2',
    }
