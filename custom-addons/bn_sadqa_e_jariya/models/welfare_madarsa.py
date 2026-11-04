from odoo import models, fields, api

class WelfareMadrasa(models.Model):
    _name = 'welfare.madrasa'
    _description = 'Madrasa Application Details'
    
    welfare_id = fields.Many2one('welfare', string='Welfare Application', required=True, ondelete='cascade')
    
    # Madrasa Info
    madarsa_name = fields.Char(string='Madrasa Name')
    city = fields.Char(string='City')
    district = fields.Char(string='District')
    total_teaching_staff = fields.Integer(string='Total Teaching Staff')
    total_salary_teaching_staff = fields.Float(string='Total Salary for Teaching Staff')
    total_non_teaching_staff = fields.Integer(string='Total Non-Teaching Staff')
    total_salary_non_teaching_staff = fields.Float(string='Total Salary for Non-Teaching Staff')
    location_link = fields.Char(string='Location Link')
    address = fields.Text(string='Address')
    tanzeem_ilhaaq = fields.Char(string='Tanzeem Ilhaaq')
    other_tanzeem_name = fields.Char(string='Other Tanzeem Name')
    province = fields.Char(string='Province')
    
    # Registration Info
    established_since = fields.Char(string='Established Since')
    ilhaaq_no = fields.Char(string='Ilhaaq No')
    registration_number = fields.Char(string='Registration Number')
    ilhaq_docs_pictures = fields.Text(string='Ilhaq Documents Pictures URLs')
    
    # Students Information
    non_resident_students = fields.Integer(string='Non-Resident Students')
    resident_students = fields.Integer(string='Resident Students')
    resident_nazra_students = fields.Integer(string='Resident Nazra Students')
    non_resident_nazra_students = fields.Integer(string='Non-Resident Nazra Students')
    resident_hifz_students = fields.Integer(string='Resident Hifz Students')
    non_resident_hifz_students = fields.Integer(string='Non-Resident Hifz Students')
    
    # Classes
    classes_oola = fields.Boolean(string='Classes Oola')
    classes_saania = fields.Boolean(string='Classes Saania')
    classes_salisa = fields.Boolean(string='Classes Salisa')
    classes_rabia = fields.Boolean(string='Classes Rabia')
    classes_khameesa = fields.Boolean(string='Classes Khameesa')
    classes_sadisa = fields.Boolean(string='Classes Sadisa')
    classes_dora_hadees = fields.Boolean(string='Classes Dora Hadees')
    classes_takhassus = fields.Boolean(string='Classes Takhassus')
    
    # Student Counts
    total_oola_students = fields.Integer(string='Total Oola Students')
    total_saania_students = fields.Integer(string='Total Saania Students')
    total_salisa_students = fields.Integer(string='Total Salisa Students')
    total_rabia_students = fields.Integer(string='Total Rabia Students')
    total_khameesa_students = fields.Integer(string='Total Khameesa Students')
    total_sadisa_students = fields.Integer(string='Total Sadisa Students')
    total_dora_hadees_students = fields.Integer(string='Total Dora Hadees Students')
    total_takhassus_students = fields.Integer(string='Total Takhassus Students')
    
    # Aims & Objectives
    objective_text = fields.Text(string='Aims and Objectives')
    
    # Construction Info (for madrasa-construction)
    area_of_madarsa = fields.Char(string='Area of Madrasa')
    value_amount_of_land_area = fields.Char(string='Value Amount of Land')
    constructed_area_estimate = fields.Char(string='Constructed Area Estimate')
    type_of_work = fields.Char(string='Type of Work')
    
    # Construction Details
    construction_iron_rods = fields.Char(string='Iron Rods')
    construction_cement_sacks = fields.Char(string='Cement Sacks')
    construction_labour_wage = fields.Char(string='Labour/Wage per Sq. Ft.')
    construction_explain_other = fields.Text(string='Explain Other Material')
    
    # Construction Pictures
    constructed_area_pictures = fields.Text(string='Constructed Area Pictures URLs')
    land_documents_pictures = fields.Text(string='Land Documents Pictures URLs')
    
    # Fund Info
    current_fund_of_madarsa = fields.Float(string='Current Fund of Madrasa')
    monthly_fund_collection = fields.Float(string='Monthly Fund Collection')
    expected_amount_from_saylani = fields.Float(string='Expected Amount from Saylani')
    ever_received_from_saylani = fields.Boolean(string='Ever Received from Saylani')
    amount_received_from_saylani = fields.Float(string='Amount Received from Saylani')
    ever_received_from_ngo = fields.Boolean(string='Ever Received from NGO')
    amount_received_from_ngo = fields.Float(string='Amount Received from NGO')
    
    # Other Help Info (for madarsa-others)
    other_help_info = fields.Text(string='Other Help Info')
    
    # Account Details
    account_cnic = fields.Char(string='Account CNIC')
    account_title = fields.Char(string='Account Title')
    account_number = fields.Char(string='Account Number')
    account_type = fields.Char(string='Account Type')

    subcategory = fields.Char(string='Subcategory')

    # Madaris Checking Form (چیکنگ فارم برائے مدارس), fields not covered above
    md_number = fields.Char(string='MD Number')
    new_code_serial = fields.Char(string='New Code / Serial No.')
    case_number = fields.Char(string='Case Number')
    request_date = fields.Date(string='Request Date')
    mohtamim_name = fields.Char(string='Mohtamim Name')
    contact_number = fields.Char(string='Contact Number')
    whatsapp_number = fields.Char(string='WhatsApp Number')
    registered_trust = fields.Char(string='Registered Trust')
    teaching_rooms = fields.Integer(string='Teaching Rooms')
    residential_rooms = fields.Integer(string='Residential Rooms')

    monthly_expense = fields.Float(string='Monthly Expense')
    exp_salaries = fields.Float(string='Salaries')
    exp_ration = fields.Float(string='Ration')
    exp_utility_bills = fields.Float(string='Gas / Electricity Bills')
    emergency_contact_if_no_support = fields.Char(string='Contacted If No Support Came')

    support_construction = fields.Char(string='Construction Support')
    support_meat = fields.Char(string='Meat Support')
    support_cooked_food = fields.Char(string='Cooked Food Support')

    student_standard = fields.Char(string='Student Standard')
    cleanliness_env = fields.Char(string='Cleanliness / Environment')
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

    total_dars_nizami = fields.Integer(string='Dars-e-Nizami Students')
    res_dars_nizami = fields.Integer(string='Dars-e-Nizami Residential')
    non_res_dars_nizami = fields.Integer(string='Dars-e-Nizami Non-Residential')
    hifz_students = fields.Integer(string='Hifz Students')
    nazra_students = fields.Integer(string='Nazra Students')
    tajweed_students = fields.Integer(string='Tajweed Students')
    school_students = fields.Integer(string='School Students')
    other_courses = fields.Integer(string='Other Courses')
    total_madrasa_students = fields.Integer(string='Total Madrasa Students')

    present_students = fields.Integer(string='Present Students')
    absent_students = fields.Integer(string='Absent Students')
    staff_dars_nizami = fields.Integer(string='Dars-e-Nizami Staff')
    staff_hifz_nazra = fields.Integer(string='Hifz / Nazra Staff')
    total_staff = fields.Integer(string='Total Staff')

    prev_test_percentage = fields.Char(string='Previous Test %')
    curr_test_percentage = fields.Char(string='Current Test %')
    org_students_count = fields.Integer(string='Organization Students')
    org_student_exam_percentage = fields.Char(string='Organization Students Exam %')
    prev_inquiry_percentage = fields.Char(string='Previous Inquiry %')
    prev_inquiry_date = fields.Char(string='Previous Inquiry Date')

    checker_opinion = fields.Text(string="Checker's Opinion")
    construction_explanation = fields.Text(string='Construction Explanation')
    checker_name_sig = fields.Char(string='Checker Name / Signature')
    board_decision = fields.Text(string='Sadqa e Jariya Board Decision')

    # Madaris Checking Form key sent by the portal -> field
    _portal_form_fields = {
        'md_number': 'md_number',
        'new_code_serial': 'new_code_serial',
        'case_number': 'case_number',
        'request_date': 'request_date',
        'jamia_name': 'madarsa_name',
        'full_address': 'address',
        'mohtamim_name': 'mohtamim_name',
        'contact_number': 'contact_number',
        'whatsapp_number': 'whatsapp_number',
        'registered_trust': 'registered_trust',
        'org_affiliation': 'tanzeem_ilhaaq',
        'established_year': 'established_since',
        'teaching_rooms': 'teaching_rooms',
        'residential_rooms': 'residential_rooms',
        'total_area': 'area_of_madarsa',
        'account_number': 'account_number',
        'cnic_number': 'account_cnic',
        'monthly_expense': 'monthly_expense',
        'exp_salaries': 'exp_salaries',
        'exp_ration': 'exp_ration',
        'exp_utility_bills': 'exp_utility_bills',
        'emergency_contact_if_no_support': 'emergency_contact_if_no_support',
        'prev_saylani_support': 'amount_received_from_saylani',
        'support_construction': 'support_construction',
        'support_meat': 'support_meat',
        'support_cooked_food': 'support_cooked_food',
        'student_standard': 'student_standard',
        'cleanliness_env': 'cleanliness_env',
        'committee_members': 'committee_members',
        'monthly_meetings': 'monthly_meetings',
        'total_dars_nizami': 'total_dars_nizami',
        'res_dars_nizami': 'res_dars_nizami',
        'non_res_dars_nizami': 'non_res_dars_nizami',
        'hifz_students': 'hifz_students',
        'nazra_students': 'nazra_students',
        'tajweed_students': 'tajweed_students',
        'school_students': 'school_students',
        'other_courses': 'other_courses',
        'total_residential': 'resident_students',
        'total_non_residential': 'non_resident_students',
        'total_madrasa_students': 'total_madrasa_students',
        'present_students': 'present_students',
        'absent_students': 'absent_students',
        'staff_dars_nizami': 'staff_dars_nizami',
        'staff_hifz_nazra': 'staff_hifz_nazra',
        'staff_non_teaching': 'total_non_teaching_staff',
        'total_staff': 'total_staff',
        'prev_test_percentage': 'prev_test_percentage',
        'curr_test_percentage': 'curr_test_percentage',
        'org_students_count': 'org_students_count',
        'org_student_exam_percentage': 'org_student_exam_percentage',
        'prev_inquiry_percentage': 'prev_inquiry_percentage',
        'prev_inquiry_date': 'prev_inquiry_date',
        'checker_opinion': 'checker_opinion',
        'construction_explanation': 'construction_explanation',
        'checker_name_sig': 'checker_name_sig',
        'board_decision': 'board_decision',
        **{f'{gender}_{level}': f'{gender}_{level}'
           for gender in ('male', 'female')
           for level in ('aidadiyah', 'aamah_1', 'aamah_2', 'khassah_1', 'khassah_2', 'aaliyah_1',
                         'aaliyah_2', 'almiyah_1', 'almiyah_2', 'takhasus_1', 'takhasus_2')},
    }