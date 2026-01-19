from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
# import pyrequests
import base64
import logging
import json


class WelfareInstitutionFetchLog(models.Model):


    _name = 'welfare.institution.fetch.log'
    _description = 'Institution Application Fetch Log'
    _order = 'fetch_date desc'

    fetch_date = fields.Datetime('Fetch Date', default=fields.Datetime.now, readonly=True)
    record_count = fields.Integer('Records Fetched', readonly=True)
    record_ids = fields.Many2many('welfare', 'welfare_fetch_log_rel', 'log_id', 'welfare_id', string='Fetched Welfare Records')
    sync = fields.Boolean('Sync')
    

    def _as_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in ['yes', 'true', '1', 'y', 't']
        return False

    def _as_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _as_int(self, value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    
    def send_welfare_sync_to_portal(self, welfare_record, endpoint_url, auth_key):
        """Send applicationId and odooId to the portal endpoint for a welfare record."""
        payload = {
            "applicationId": welfare_record.old_system_id,
            "odooId": str(welfare_record.id)
        }
        data = json.loads(json.dumps(payload, default=str))

        headers = {
            'x-odoo-auth-key': auth_key,
            'Content-Type': 'application/json'
        }
        # raise UserError(f"Payload: {data} headers: {headers} endpoint: {endpoint_url}")
        try:

            response = requests.post(endpoint_url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            # raise UserError(f"Response: {response.text} only data {response.json().get('data', [])}")
            # return {'_id': '68df61d0de766806173de562', 'syncedToOdoo': True, 'category': 'masjid', 'subCategory': 'masjid-wages', 'province': 'Punjab', 'form': {'category': 'masjid', 'subcategory': 'masjid-wages', 'applicantInformation': {'name': 'Ipsa ullam nulla am', 'designation': 'Voluptate iste omnis', 'phoneNumber': 'Eaque unde modi veli', 'whatsappNumber': 'Ad sed veritatis qui', 'applicantLocationLink': 'https://www.nad.ca'}, 'committeeMembers': [{}, {}, {}], 'masjidInfo': {'masjidName': 'TEST_MASJID_RECORD_2', 'city': 'Ullamco fuga Conseq', 'district': 'Sint quibusdam sit ', 'totalNummberOfStaff': '40', 'totalSalaryExpenseForStaff': '47', 'locationLink': 'https://www.hyrudexat.ws', 'address': 'Ut dolor enim soluta', 'province': 'Punjab'}, 'prayersInfo': {'fajr': 'Yes', 'zuhr': 'No', 'asr': 'Yes', 'maghrib': 'No', 'isha': 'Yes', 'jumma': 'No'}, 'expenditureInfo': {'monthlyFundOfMasjid': '9', 'funcofmajidFromBoxes': '74', 'shopswithinMasjidPremises': 'No', 'totalexpenditure': '14'}, 'fundInfo': {'howMuchamountareyouexpectingfromSaylani': '33', 'everReceivedFromSaylani': 'No', 'everReceivedFromNGO': 'Yes', 'amountReceivedFromNGO': '23'}, 'accountDetails': {'accountCnic': 'Ut non ex laudantium', 'accountTitle': 'Temporibus consequat', 'accountNumber': 'Irure dolor providen', 'accountType': 'UBL OMNI'}}, 'status': 'hod-review', 'token': 'PUN-20251003-0037', 'inquiryReport': {'images': [], 'verified': False}, 'submittedBy': '68beab1622daff30a9a44ad7', 'lastUpdatedBy': '68beab1622daff30a9a44ad7', 'inquiryReports': [{'status': 'completed', 'images': [], 'verified': False, 'officerId': '68e4da8dd497ae9e1660e445', '_id': '68df6491de766806173de5dc', 'createdAt': '2025-10-03T05:52:17.584Z', 'updatedAt': '2025-10-03T05:52:25.311Z', 'content': 'abcde'}], 'hodReviews': [{'comments': '', '_id': '68df6491de766806173de5dd'}], 'trusteeReviews': [{'comments': '', '_id': '68df6491de766806173de5de'}], 'fundingPlans': [], 'createdAt': '2025-10-03T05:40:32.879Z', 'updatedAt': '2026-01-02T11:27:09.434Z', '__v': 1, 'syncedFromOdoo': False, 'odooId': 41}
            return response.json().get('data', [])
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to sync welfare record {welfare_record.id} to portal: {e}")
            return None    
    
    def action_view_fetched_records(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fetched Welfare Records',
            'res_model': 'welfare',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.record_ids.ids)],
            'target': 'current',
        }
        
    def download_image(self, url):
        try:
            if url and url.startswith('http'):
                img_resp = requests.get(url, timeout=20)
                if img_resp.status_code == 200:
                    return base64.b64encode(img_resp.content)
        except Exception:
            pass
        return None
        
    @api.model
    def fetch_institution_applications(self):
        company = self.env.company
        endpoint = company.welfare_institution_endpoint
        base_url = company.welfare_instituiton_url
        url = f"{base_url}{endpoint}"
        headers = {
            'x-odoo-auth-key': f'{company.odoo_auth_institution_key}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json().get('data', [])
        except Exception as e:
            raise UserError(f"Institution fetch failed: {str(e)}")
        
        created_ids = []
        Employee = self.env['hr.employee']
        Partner = self.env['res.partner']
        Welfare = self.env['welfare']
        all_synced = True

        for rec in data:
            submitted = rec.get('submittedBy', {})
            raw_cnic = submitted.get('cnic')
            if raw_cnic and raw_cnic.isdigit() and len(raw_cnic) == 13:
                formatted_cnic = f"{raw_cnic[:5]}-{raw_cnic[5:12]}-{raw_cnic[12:]}"
            else:
                formatted_cnic = ''
                
            cnic = formatted_cnic
            partner = None
            if cnic:
                partner = Partner.search([('cnic_no', '=', cnic)], limit=1)
            if not partner:
                # Download CNIC images if available
                cnic_front_url = submitted.get('cnicFront')
                cnic_back_url = submitted.get('cnicBack')
                profile_image_url = submitted.get('profileImage')

                cnic_front_image = self.download_image(cnic_front_url)
                cnic_back_image = self.download_image(cnic_back_url)
                profile_image = self.download_image(profile_image_url)  
                # Create new Donee
                partner_vals = {
                    'image_1920': profile_image,
                    'name': submitted.get('fullname') or rec.get('form', {}).get('applicantInformation', {}).get('name', 'Unknown'),
                    'cnic_no': cnic,
                    'mobile': submitted.get('whatsapp') or submitted.get('phoneNumber'),
                    'email': submitted.get('email'),
                    'cnic_front_image': cnic_front_image,
                    'cnic_back_image': cnic_back_image,
                    'category_id': [(6, 0, [self.env.ref('bn_profile_management.donee_partner_category').id]), 
                                    (6, 0, [self.env.ref('bn_profile_management.welfare_partner_category').id])
                                    ],
                }
                partner = Partner.create(partner_vals)

            # Inquiry Officer (from inquiryReports[0].officerId)
            inquiry_officer = None
            inquiry_reports = rec.get('inquiryReports', [])
            officer_data = None
            if inquiry_reports:
                officer_data = inquiry_reports[0].get('officerId')
            if officer_data:
                officer_email = officer_data.get('email')
                officer_name = officer_data.get('fullname')
                # Try to find by email first, then by name
                if officer_email:
                    inquiry_officer = Employee.search([('work_email', '=', officer_email)], limit=1)
                if not inquiry_officer and officer_name:
                    inquiry_officer = Employee.search([('name', '=', officer_name)], limit=1)
                if not inquiry_officer:
                    # Create new employee
                    emp_vals = {
                        'name': officer_name or 'Unknown',
                        'work_email': officer_email,
                        'category_ids': [(6, 0, [self.env.ref('bn_welfare.inquiry_officer_hr_employee_category').id])],
                    }
                    inquiry_officer = Employee.create(emp_vals)

            # Parse form data based on category
            form_data = rec.get('form', {})
            category = rec.get('category')
            subcategory = rec.get('subCategory')
            
            # Get common data
            applicant_info = form_data.get('applicantInformation', {})
            fund_info = form_data.get('fundInfo', {})
            account_details = form_data.get('accountDetails', {})
            
            # Create welfare record
            vals = {
                'donee_id': partner.id if partner else False,
                'employee_id': inquiry_officer.id if inquiry_officer else False,
                'old_system_id': rec.get('_id'),
                'designation': applicant_info.get('designation'),
                'institution_category': category,
                'subcategory': subcategory,
                'aid_from_other_organization': 'yes' if self._as_bool(fund_info.get('everReceivedFromSaylani', '')) else 'no',
                'monthly_income': self._as_float(fund_info.get('amountReceivedFromSaylani', 0)),
                'bank_account': 'yes' if account_details.get('accountType') else 'no',
                'bank_name': account_details.get('accountTitle'),
                'account_no': account_details.get('accountNumber'),
                'state': 'inquiry',
                'portal_application_id': rec.get('token'),
                'hod_remarks': rec.get('hodReviews', [{}])[0].get('comments', ''),
            }
            
            # Set institute name and address based on category
            if category == 'masjid':
                masjid_info = form_data.get('masjidInfo', {})
                vals.update({
                    'institute_name': masjid_info.get('masjidName'),
                    'company_address': masjid_info.get('address'),
                })
            elif category == 'madrasa':
                madrasa_info = form_data.get('madrasaInfo', {})
                vals.update({
                    'institute_name': madrasa_info.get('madarsaName'),
                    'company_address': madrasa_info.get('address'),
                })
            
            welfare = Welfare.create(vals)
            
            # Create Committee Members
            committee_members = form_data.get('committeeMembers', [])
            for member in committee_members:
                if member and member.get('committeeMemberName'):
                    self.env['welfare.committee.member'].create({
                        'welfare_id': welfare.id,
                        'name': member.get('committeeMemberName'),
                        'designation': member.get('designation'),
                        'educational_qualification': member.get('educationalQualification'),
                        'cnic': member.get('cnic'),
                        'phone': member.get('phonenumber'),
                    })
            
            # Create Teachers (for madrasa)
            if category == 'madrasa':
                teachers = form_data.get('teachers', [])
                for teacher in teachers:
                    if teacher and teacher.get('teacherName'):
                        self.env['welfare.teacher'].create({
                            'welfare_id': welfare.id,
                            'name': teacher.get('teacherName'),
                            'designation': teacher.get('designation'),
                            'educational_qualification': teacher.get('educationalQualification'),
                            'other_degree_name': teacher.get('otherDegreeName'),
                            'cnic': teacher.get('cnic'),
                            'phone': teacher.get('phonenumber'),
                        })
                
                # Create Madrasa Details
                self._create_madrasa_details(welfare, form_data, rec)
            
            elif category == 'masjid':
                # Create Masjid Details
                self._create_masjid_details(welfare, form_data, rec)
            
            # Create Inquiry Reports
            for inquiry in inquiry_reports:
                officer_data = inquiry.get('officerId', {})
                self.env['welfare.inquiry.report'].create({
                    'welfare_id': welfare.id,
                    'status': inquiry.get('status'),
                    'images': str(inquiry.get('images', [])),
                    'verified': inquiry.get('verified', False),
                    'officer_name': officer_data.get('fullname'),
                    'officer_email': officer_data.get('email'),
                    'content': inquiry.get('content', ''),
                    'external_id': inquiry.get('_id'),
                    'create_date': inquiry.get('createdAt'),
                    'write_date': inquiry.get('updatedAt'),
                })
            
            created_ids.append(welfare.id)
            
            # Send sync to portal
            sync_endpoint = f"{base_url}{company.mark_institution_application_endpoint}"
            sync_applications = self.send_welfare_sync_to_portal(
                welfare_record=welfare,
                endpoint_url=sync_endpoint,
                auth_key=company.odoo_auth_institution_key
            )
            
            response_status = False
            if sync_applications and isinstance(sync_applications, dict):
                response_status = sync_applications.get("syncedToOdoo", False)
            if response_status:
                welfare.write({'is_synced': True})
            else:
                all_synced = False

        log = self.create({
            'record_count': len(created_ids),
            'record_ids': [(6, 0, created_ids)],
        })
        
        if all_synced and created_ids:
            log.sync = True
            
        return log

    def _create_masjid_details(self, welfare, form_data, rec):
        """Create masjid details record"""
        masjid_info = form_data.get('masjidInfo', {})
        prayers_info = form_data.get('prayersInfo', {})
        construction_info = form_data.get('constructionInfoOfMasjid', {})
        construction_details = form_data.get('constructionDetails', {})
        expenditure_info = form_data.get('expenditureInfo', {})
        fund_info = form_data.get('fundInfo', {})
        account_details = form_data.get('accountDetails', {})
        other_help = form_data.get('otherHelpInfoSection', {})
        
        masjid_vals = {
            'welfare_id': welfare.id,
            'subcategory': rec.get('subCategory'),
            'masjid_name': masjid_info.get('masjidName'),
            'city': masjid_info.get('city'),
            'district': masjid_info.get('district'),
            'total_number_of_staff': self._as_int(masjid_info.get('totalNummberOfStaff')),
            'total_salary_expense_for_staff': self._as_float(masjid_info.get('totalSalaryExpenseForStaff')),
            'location_link': masjid_info.get('locationLink'),
            'address': masjid_info.get('address'),
            'province': masjid_info.get('province'),
            'masjid_pictures': str(masjid_info.get('masjidPicture', [])),
            
            # Prayers Info
            'fajr': self._as_bool(prayers_info.get('fajr')),
            'zuhr': self._as_bool(prayers_info.get('zuhr')),
            'asr': self._as_bool(prayers_info.get('asr')),
            'maghrib': self._as_bool(prayers_info.get('maghrib')),
            'isha': self._as_bool(prayers_info.get('isha')),
            'jumma': self._as_bool(prayers_info.get('jumma')),
            'people_in_jamat_jumma': self._as_int(prayers_info.get('peopleInJamatForJumma')),
            'people_in_jamat_fajr': self._as_int(prayers_info.get('peopleInJamatForFajr')),
            'people_in_jamat_zuhr': self._as_int(prayers_info.get('peopleInJamatForZuhr')),
            'people_in_jamat_asr': self._as_int(prayers_info.get('peopleInJamatForAsr')),
            'people_in_jamat_maghrib': self._as_int(prayers_info.get('peopleInJamatForMaghrib')),
            'people_in_jamat_isha': self._as_int(prayers_info.get('peopleInJamatForIsha')),
            
            # Construction Info
            'area_of_masjid': self._as_float(construction_info.get('areaofMasjid')),
            'constructed_area_of_masjid': self._as_float(construction_info.get('constructedAreaofMasjid')),
            'value_amount_of_land': self._as_float(construction_info.get('valueAmountOfLandOfMasjid')),
            'remaining_work': construction_info.get('remainingWorkofmasjid'),
            
            # Construction Details
            'iron_rods': construction_details.get('ironRods'),
            'cement_sacks': construction_details.get('cementSacks'),
            'labour_wage_per_sqft': construction_details.get('labour/wagepersquarefeet'),
            'explain_other_material': construction_details.get('explainOtherMaterial'),
            
            # Construction Pictures
            'constructed_area_pictures': str(rec.get('contructedAreaPictures', [])),
            'land_documents_pictures': str(rec.get('landDocumentsPictures', [])),
            
            # Expenditure Info
            'monthly_fund_of_masjid': self._as_float(expenditure_info.get('monthlyFundOfMasjid')),
            'func_of_masjid_from_boxes': self._as_float(expenditure_info.get('funcofmajidFromBoxes')),
            'shops_within_masjid_premises': self._as_bool(expenditure_info.get('shopswithinMasjidPremises')),
            'total_expenditure': self._as_float(expenditure_info.get('totalexpenditure')),
            
            # Fund Info
            'expected_amount_from_saylani': self._as_float(fund_info.get('howMuchamountareyouexpectingfromSaylani')),
            'ever_received_from_saylani': self._as_bool(fund_info.get('everReceivedFromSaylani')),
            'amount_received_from_saylani': self._as_float(fund_info.get('amountReceivedFromSaylani')),
            'ever_received_from_ngo': self._as_bool(fund_info.get('everReceivedFromNGO')),
            'amount_received_from_ngo': self._as_float(fund_info.get('amountReceivedFromNGO')),
            
            # Other Help Info
            'other_help_info': other_help.get('otherHelpInfo'),
            
            # Account Details
            'account_cnic': account_details.get('accountCnic'),
            'account_title': account_details.get('accountTitle'),
            'account_number': account_details.get('accountNumber'),
            'account_type': str(account_details.get('accountType')),
        }
        
        self.env['welfare.masjid'].create(masjid_vals)

    def _create_madrasa_details(self, welfare, form_data, rec):
        """Create madrasa details record"""
        madrasa_info = form_data.get('madrasaInfo', {})
        registration_info = form_data.get('registrationInfo', {})
        students_info = form_data.get('studentsInformation', {})
        aims_objectives = form_data.get('aimsAndObjectives', {})
        construction_info = form_data.get('constructionInfoOfMadarsa', {})
        construction_details = form_data.get('constructiondDetails', {})
        fund_info = form_data.get('fundInfo', {})
        account_details = form_data.get('accountDetails', {})
        other_help = form_data.get('otherHelpInfoSection', {})
        
        madrasa_vals = {
            'welfare_id': welfare.id,
            'subcategory': rec.get('subCategory'),
            'madarsa_name': madrasa_info.get('madarsaName'),
            'city': madrasa_info.get('city'),
            'district': madrasa_info.get('district'),
            'total_teaching_staff': self._as_int(madrasa_info.get('totalNumberOfTeachingStaff')),
            'total_salary_teaching_staff': self._as_float(madrasa_info.get('totalSalaryExpenseForTeachingStaff')),
            'total_non_teaching_staff': self._as_int(madrasa_info.get('totalNumberOfNonTeachingStaff')),
            'total_salary_non_teaching_staff': self._as_float(madrasa_info.get('totalSalaryExpenseNonForTeachingStaff')),
            'location_link': madrasa_info.get('locationLink'),
            'address': madrasa_info.get('address'),
            'tanzeem_ilhaaq': madrasa_info.get('tanzeemIlhaaq'),
            'other_tanzeem_name': madrasa_info.get('otherTanzeemName'),
            'province': madrasa_info.get('province'),
            
            # Registration Info
            'established_since': registration_info.get('establishedSince'),
            'ilhaaq_no': registration_info.get('ilhaaqNo'),
            'registration_number': registration_info.get('registrationNumber'),
            'ilhaq_docs_pictures': str(registration_info.get('ilhaqDocsPictures', [])),
            
            # Students Information
            'non_resident_students': self._as_int(students_info.get('numberOfNonResidentStudents')),
            'resident_students': self._as_int(students_info.get('numberOfResidentStudents')),
            'resident_nazra_students': self._as_int(students_info.get('numberOfResidentNazraStudents')),
            'non_resident_nazra_students': self._as_int(students_info.get('numberOfNonResidentNazraStudents')),
            'resident_hifz_students': self._as_int(students_info.get('numberOfResidentHifzStudents')),
            'non_resident_hifz_students': self._as_int(students_info.get('numberOfNonResidentHifzStudents')),
            
            # Classes
            'classes_oola': self._as_bool(students_info.get('classesOola')),
            'classes_saania': self._as_bool(students_info.get('classesSaania')),
            'classes_salisa': self._as_bool(students_info.get('classesSalisa')),
            'classes_rabia': self._as_bool(students_info.get('classesRabia')),
            'classes_khameesa': self._as_bool(students_info.get('classesKhameesa')),
            'classes_sadisa': self._as_bool(students_info.get('classesSadisa')),
            'classes_dora_hadees': self._as_bool(students_info.get('classesDoraHadees')),
            'classes_takhassus': self._as_bool(students_info.get('classesTakhassus')),
            
            # Student Counts
            'total_oola_students': self._as_int(students_info.get('totalOolaStudents')),
            'total_saania_students': self._as_int(students_info.get('totalSaaniaStudents')),
            'total_salisa_students': self._as_int(students_info.get('totalSalisaStudents')),
            'total_rabia_students': self._as_int(students_info.get('totalRabiaStudents')),
            'total_khameesa_students': self._as_int(students_info.get('totalKhameesaStudents')),
            'total_sadisa_students': self._as_int(students_info.get('totalSadisaStudents')),
            'total_dora_hadees_students': self._as_int(students_info.get('totalDoraHadeesStudents')),
            'total_takhassus_students': self._as_int(students_info.get('totalTakhassusStudents')),
            
            # Aims & Objectives
            'objective_text': aims_objectives.get('objectiveTextArea'),
            
            # Construction Info
            'area_of_madarsa': construction_info.get('areaofMadarsa'),
            'value_amount_of_land_area': construction_info.get('valueAmountOfLandAreq'),
            'constructed_area_estimate': construction_info.get('constructedAreaEstimate'),
            'type_of_work': construction_info.get('typeOfWork'),
            
            # Construction Details
            'construction_iron_rods': construction_details.get('ironRods'),
            'construction_cement_sacks': construction_details.get('cementSacks'),
            'construction_labour_wage': construction_details.get('labour/wagepersquarefeet'),
            'construction_explain_other': construction_details.get('explainOtherMaterial'),
            
            # Construction Pictures
            'constructed_area_pictures': str(rec.get('contructedAreaPictures', [])),
            'land_documents_pictures': str(rec.get('landDocumentsPictures', [])),
            
            # Fund Info
            'current_fund_of_madarsa': self._as_float(fund_info.get('currentFundOfMadarsa')),
            'monthly_fund_collection': self._as_float(fund_info.get('monthlyFundCollection')),
            'expected_amount_from_saylani': self._as_float(fund_info.get('howMuchamountareyouexpectingfromSaylani')),
            'ever_received_from_saylani': self._as_bool(fund_info.get('everReceivedFromSaylani')),
            'amount_received_from_saylani': self._as_float(fund_info.get('amountReceivedFromSaylani')),
            'ever_received_from_ngo': self._as_bool(fund_info.get('everReceivedFromNGO')),
            'amount_received_from_ngo': self._as_float(fund_info.get('amountReceivedFromNGO')),
            
            # Other Help Info
            'other_help_info': other_help.get('otherHelpInfo'),
            
            # Account Details
            'account_cnic': account_details.get('accountCnic'),
            'account_title': account_details.get('accountTitle'),
            'account_number': account_details.get('accountNumber'),
            'account_type': str(account_details.get('accountType')),
        }
        
        self.env['welfare.madrasa'].create(madrasa_vals)