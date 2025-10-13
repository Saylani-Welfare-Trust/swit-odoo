/** @odoo-module **/
import { SaleOrderManagementControlPanel } from "@pos_sale/app/order_management_screen/sale_order_management_control_panel/sale_order_management_control_panel";


export class FeeVoucherManagementControlPanel extends SaleOrderManagementControlPanel {
    // static template = "pos_enhancement.feeVoucherManagementScreen";
    setup() {
        super.setup();
        console.log("FeeVoucherManagementControlPanel")
    }
    _computeDomain() {
        let domain = [
            ["state", "!=", "cancel"],
            ["invoice_status", "!=", "invoiced"],
            ['is_fee_voucher','=',true],
        ];
        const input = this.pos.orderManagement.searchString.trim();
        if (!input) {
            return domain;
        }
        console.log("domain 1",domain)
        const searchConditions = this.pos.orderManagement.searchString.split(/[,&]\s*/);
        // console.log("searchConditions",searchConditions)
        if (searchConditions.length === 1) {
            console.log("domain 2",domain)
            const cond = searchConditions[0].split(/:\s*/);
            if (cond.length === 1) {
                domain = domain.concat(Array(this.searchFields.length - 1).fill("|"));
                console.log("domain 3",domain)
                domain = domain.concat(
                    this.searchFields.map((field) => [field, "ilike", `%${cond[0]}%`])
                );
                console.log("domain 4",domain)
                // console.log('domain',domain)
                return domain;
            }
        }
        
        for (const cond of searchConditions) {
            console.log("domain 5",domain)
            const [tag, value] = cond.split(/:\s*/);
            if (!this.validSearchTags.has(tag)) {
                continue;
            }
            domain.push([this.fieldMap[tag], "ilike", `%${value}%`]);
            console.log("domain 6",domain)
        }
        console.log('domain 7',domain)
        return domain;
    }

}