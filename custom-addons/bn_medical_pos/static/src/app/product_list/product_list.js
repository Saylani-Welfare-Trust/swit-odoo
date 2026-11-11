/** @odoo-module */

import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";
import { patch } from "@web/core/utils/patch";

// A medical counter opens on a category: show the other categories next to it, so a category
// switched on in Medical & Health > Configuration > Categories appears right away.
patch(ProductsWidget.prototype, {
    getCategories() {
        const categories = super.getCategories(...arguments);
        const db = this.pos.db;
        const selectedId = this.pos.selectedCategoryId;
        if (
            !this.pos.config.is_medical_pos ||
            selectedId === db.root_category_id ||
            db.get_category_childs_ids(selectedId).length
        ) {
            return categories;
        }
        const shown = new Set(categories.map((category) => category.id));
        const siblings = db
            .get_category_childs_ids(db.get_category_parent_id(selectedId))
            .filter((id) => !shown.has(id))
            .map((id) => db.category_by_id[id])
            .filter(Boolean)
            .map((category) => ({
                id: category.id,
                name: category.name,
                icon: "",
                separator: "fa-caret-right",
                showSeparator: false,
                imageUrl:
                    category.has_image &&
                    `/web/image?model=pos.category&field=image_128&id=${category.id}&unique=${category.write_date}`,
            }));
        return [...categories, ...siblings];
    },
});
