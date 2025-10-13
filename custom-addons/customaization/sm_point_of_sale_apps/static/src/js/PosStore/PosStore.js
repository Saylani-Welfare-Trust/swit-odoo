/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.selectedStockMoveCategoryId = 0;
        this.searchStockMoveProductWord = "";
    },
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.res_company_branch = loadedData["res_company_branch"];
    },
    setSelectedStockMoveCategoryId(categoryId) {
        this.selectedStockMoveCategoryId = categoryId;
    },
    resetProductStockMoveScreenSearch() {
        this.searchStockMoveProductWord = "";
        const { start_category, iface_start_categ_id } = this.config;
        this.selectedStockMoveCategoryId = (start_category && iface_start_categ_id?.[0]) || 0;
    }
});
