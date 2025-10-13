/** @odoo-module */
import { registry } from "@web/core/registry";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { ProductStockMoveScreenList } from "@sm_point_of_sale_apps/js/CustomProductList/ProductStockMoveScreenList";
import { Component, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ProductStockMoveScreen extends Component {
    static template = "sm_point_of_sale_apps.ProductStockMoveScreen";
    static components = {
        ProductStockMoveScreenList,
    };
    setup() {
        super.setup();
        this.pos = usePos();

    }
}
registry.category("pos_screens").add("ProductStockMoveScreen", ProductStockMoveScreen);