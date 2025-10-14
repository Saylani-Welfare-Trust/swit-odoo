
{
	"name"         	: "Customization POS",
	"category"     	: "BytesNode/Customization POS",
	"version"      	: "1.0.0",
	"sequence"     	: 1,
    "depends"		: ['web','base','product','account','pos_customer_feedback'],
	"data"         	: [
	  'security/ir.model.access.csv',
      'views/product.xml',
    #   'views/pos_order.xml',
	],
	"installable"  : True,
}
