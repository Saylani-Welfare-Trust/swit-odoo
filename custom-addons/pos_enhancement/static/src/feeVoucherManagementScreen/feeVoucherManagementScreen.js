/** @odoo-module **/

import { registry } from "@web/core/registry";

import { SaleOrderManagementScreen } from "@pos_sale/app/order_management_screen/sale_order_management_screen/sale_order_management_screen";
import { Component, onMounted, useRef } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";
import { FeeVoucherManagementControlPanel } from "../feeVoucherManagementControl/feeVoucherManagementScreen";



export class FeeVoucherManagementScreen extends SaleOrderManagementScreen {
    static template = "pos_enhancement.feeVoucherManagementScreen";
    static components = {
        ...SaleOrderManagementScreen.components,
        FeeVoucherManagementControlPanel,
    };
    setup() {
        super.setup();
        console.log("FeeVoucherManagementScreen")
        this.saleOrderFetcher = useService("fee_voucher_fetcher_service");
        useBus(this.saleOrderFetcher, "update", this.render);

        onMounted(this.onMounted);
    }
    get orders() {
        const orders=this.saleOrderFetcher.get();
        console.log('orders',orders)
        return orders
    }
}

registry.category("pos_screens").add("FeeVoucherManagementScreen", FeeVoucherManagementScreen);
