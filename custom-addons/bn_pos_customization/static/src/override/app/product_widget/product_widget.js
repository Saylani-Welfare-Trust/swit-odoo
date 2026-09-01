/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";

patch(ProductsWidget.prototype, {
    get productsToDisplay() {
        const { db } = this.pos;
        let list = [];
        var parent_check = db.get_category_by_id(this.selectedCategoryId)

        if (this.searchWord !== "") {
            list = db.search_product_in_category(this.selectedCategoryId, this.searchWord);
        } else {
            if (parent_check.name == "Root") {
                list = []
            }
            else if (!parent_check.child_id || parent_check.child_id.length === 0) {
                list = db.get_product_by_category(this.selectedCategoryId);
            } else {
                list = [];
            }
        }
        
        return list.sort(function (a, b) {
            return a.display_name.localeCompare(b.display_name);
        });
    }
})