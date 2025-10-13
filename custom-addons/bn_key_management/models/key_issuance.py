from odoo import fields, models, api, exceptions


key_selection = [('draft', 'Draft'), ('issued', 'Issued'), ('donation_receive', 'Donation Received'), ('returned', 'Returned'), ('overdue', 'Overdue')]


class KeyIssuance(models.Model):
    _name = 'key.issuance'
    _description = 'Key Issuance'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'rider_name'


    rider_name = fields.Char(related='rider_id.name', string="Rider", store=True)
    
    key_id = fields.Many2one('key', string="Key ID", tracking=True)
    rider_id = fields.Many2one(related='key_id.rider_id', string="Rider ID", store=True)

    donation_box_id = fields.Many2one(related='key_id.donation_box_registration_id', string="Donation Box Registartion ID", store=True, tracking=True)

    box_no = fields.Char(related='donation_box_id.lot_id.name', string='Box No', store=True, tracking=True)
    name = fields.Char(related='donation_box_id.name', string='Requestor Name', store=True, tracking=True)
    contact_no = fields.Char(related='donation_box_id.contact_no', string='Contact No', store=True, tracking=True)
    location = fields.Char(related='donation_box_id.location', string='Requested Location', store=True, tracking=True)
    contact_person_name = fields.Char(related='donation_box_id.contact_person_name', string='Contact Person', store=True, tracking=True)

    installer_id = fields.Many2one(related='donation_box_id.installer_id', string="Installer ID")
    zone_id = fields.Many2one(related='donation_box_id.zone_id', string="Zone ID", store=True, tracking=True)
    city_id = fields.Many2one(related='donation_box_id.city_id', string="City ID", store=True, tracking=True)
    donor_id = fields.Many2one(related='donation_box_id.donor_id', string="Donor ID", store=True, tracking=True)
    sub_zone_id = fields.Many2one(related='donation_box_id.sub_zone_id', string="Sub Zone ID", store=True, tracking=True)
    donation_box_request_id = fields.Many2one(related='donation_box_id.donation_box_request_id', string="Donation Box Request ID", store=True)
    product_id = fields.Many2one(related='donation_box_id.product_id', string="Donation Box Category ID", store=True, tracking=True)
    installation_category_id = fields.Many2one(related='donation_box_id.installation_category_id', string="Installation Category ID", store=True, tracking=True)

    installation_date = fields.Date(related='donation_box_id.installation_date', string='Installation Date', store=True, tracking=True)


    issued_on = fields.Datetime(string="Issued On", default=fields.Datetime.now)
    returned_on = fields.Datetime(string="Returned On")
    
    state = fields.Selection(selection=key_selection, default='draft', string="Status")

    donation_amount = fields.Float('Donation Amount', tracking=True)


    def action_key_issued(self):
        for record in self:
            if self.search([('key_id', '=', record.key_id.id), ('state', '=', 'issued')]):
                raise exceptions.ValidationError(str(f'Key ( {record.key_id.name} ) is already issued to {record.rider_id.name}'))

            record.state = 'issued'
            record.key_id.state = 'issued'
            record.key_id.donation_box_registration_id.city_id = record.key_id.key_location_id.city_id.id
            record.key_id.donation_box_registration_id.zone_id = record.key_id.key_location_id.zone_id.id
            record.key_id.donation_box_registration_id.sub_zone_id = record.key_id.key_location_id.sub_zone_id.id

    def action_return_key(self):
        for record in self:
            if not record.donation_amount:
                raise exceptions.ValidationError(str(f'Please enter the Amount of Donation Collected against key ( {self.key_id.name} )'))

            record.state = 'returned'
            record.returned_on = fields.Datetime.now()
            record.key_id.state = 'available'

    def action_donation_receive(self):
        for rec in self:
            rec.state = 'donation_receive'

    def action_overdue(self):
        for record in self:
            record.state = 'overdue'

    def _create_donation_journal_entry(self, amount):
        """Create journal entry for donation amount"""
        AccountMove = self.env['account.move']
        
        # Get the donation journal (cash journal or create one if needed)
        journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        analytical = self.env['donation.box.registration'].search([
            ('box_no', '=', self.box_no),
        ], limit=1)
        
        if not journal:
            journal = self.env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
        
        if not journal:
            raise exceptions.ValidationError("No cash or bank journal found for creating donation entry")

        # Get accounts - you may need to adjust these based on your chart of accounts
        # Cash/Bank account (debit)
        bank_account = journal.default_account_id
        if not bank_account:
            raise exceptions.ValidationError("Journal does not have a bank account configured")

        # Donation Revenue account (credit) - adjust account code as per your setup
        # Get the income account from the product template
        product = self.product_id if self.product_id else False
        donation_account = product.property_account_income_id or product.categ_id.property_account_income_categ_id if product else False

        if not donation_account:
            raise exceptions.ValidationError("No income account configured on the product or its category.")

        # Create journal entry
        journal_entry = AccountMove.create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f'Donation Box Collection - {self.box_no} from {self.donor_id.name if self.donor_id else "Unknown"}',
            'line_ids': [
                (0, 0, {
                    'name': f'Donation Collection - Box {self.box_no}',
                    'account_id': bank_account.id,
                    'debit': amount,
                    'credit': 0.0,
                    'partner_id': self.donor_id.id if self.donor_id else False,
                    'analytic_distribution': {analytical.analytic_plan_id.id: 100} if analytical and analytical.analytic_plan_id else {},
                }),
                (0, 0, {
                    'name': f'Donation Revenue - Box {self.box_no}',
                    'account_id': donation_account.id,
                    'debit': 0.0,
                    'credit': amount,
                    'partner_id': self.donor_id.id if self.donor_id else False,
                    'analytic_distribution': {analytical.analytic_plan_id.id: 100} if analytical and analytical.analytic_plan_id else {},

                })
            ]
        })
        
        # Post the journal entry
        journal_entry.action_post()
        
        return journal_entry.id

    @api.model
    def set_donation_amount(self, data):
        if not data:
            return {
                "status": "error",
                "body": "Please specify Key and Collection Amount",
            }

        collection = self.env['rider.collection'].search([('box_no', '=', data['key']), ('state', '=', 'donation_submit'), ('date', '=', fields.Date.today())])
        
        if not collection:
            return {
                "status": "error",
                "body": f"Please first submit your Collection aganist {data['key']}",
            }
        elif collection and collection.amount != float(data['amount']):
            return {
                "status": "error",
                "body": f"Please enter the correct amount collected against {data['key']}",
            }

        collection.state = 'paid'


        key_obj = self.sudo().search([('key_id.box_no', '=', data['key']), ('state', '=', 'issued')])

        if not key_obj:
            return {
            "status": "error",
            "body": "Invalid Donation Box",
            }

        key_obj.donation_amount = data['amount']
        key_obj.action_donation_receive()

        # Create Journal Entry for the donation amount
        if float(data['amount']) > 0:
            try:
                journal_entry_id = key_obj._create_donation_journal_entry(float(data['amount']))
                return {
                    "status": "success",
                    "DonationBox_id": key_obj.id,
                    "journal_entry_id": journal_entry_id,
                }
            except Exception as e:
                return {
                    "status": "error",
                    "body": f"Donation recorded but failed to create journal entry: {str(e)}",
                }

        return {
            "status": "success",
            "DonationBox_id": key_obj.id,
        }