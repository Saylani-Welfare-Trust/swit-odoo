/** @odoo-module */
import { registry } from "@web/core/registry";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { CategorySummaryButton } from "@advanced_pos_reports/js/Category";
import { LocationSummaryButton } from "@advanced_pos_reports/js/Location";
import { OrderSummaryButton } from "@advanced_pos_reports/js/Order";
import { PaymentSummaryButton } from "@advanced_pos_reports/js/Payment";
import { ProductSummaryButton } from "@advanced_pos_reports/js/Product";
import { Component, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CustomReportsScreen extends Component {
    static template = "sm_point_of_sale_apps.CustomReportsScreen";
    static components = {
        CategorySummaryButton,
        LocationSummaryButton,
        OrderSummaryButton,
        PaymentSummaryButton,
        ProductSummaryButton,
    };
    setup() {
        super.setup();
        this.pos = usePos();

    }
}
registry.category("pos_screens").add("CustomReportsScreen", CustomReportsScreen);