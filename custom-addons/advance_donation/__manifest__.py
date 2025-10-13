
{
	"name"         : "Advance Donation",
	"category"     : "BytesNode/Advance Donation",
	"version"      : "1.0.0",
	"sequence"     : 1,
    "depends"      : ['web','base','point_of_sale','product','account','base_account_budget'],
	"data"         : [
	  'security/ir.model.access.csv',
    'views/advance_donation_view.xml',
    'views/donation_credit.xml',
    'views/product_template.xml',
    'views/schdular.xml',
    'views/posmakepayment.xml',
    'views/aprroval_views.xml',
    'views/email_template.xml',
    'views/pos_order.xml',
	  'views/analytic_view.xml',
	],
	"installable"  : True,
  'license': 'AGPL-3',
}
