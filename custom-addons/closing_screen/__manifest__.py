
{
	"name"         	: "Closing Screen",
	"category"     	: "BytesNode/Customization POS",
	"version"      	: "1.0.0",
	"sequence"     	: 1,
    "depends"		: ['web','base','product','account','point_of_sale'],
	"data"         	: [
	  'security/ir.model.access.csv',
      'wizard/closingscreen.xml',
      'views/closemaster.xml',
	],
	"installable"  : True,
}
