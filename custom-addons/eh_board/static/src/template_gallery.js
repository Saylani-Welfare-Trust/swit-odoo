/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * Template gallery: pick a ready-made vertical dashboard (or a saved one) and
 * spin up a live board from it. Packs whose base app is not installed show as
 * unavailable rather than failing. */

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

const CATEGORY_LABELS = {
    general: "General", account: "Accounting", crm: "Sales & CRM",
    pos: "Point of Sale", stock: "Inventory", hr: "Human Resources", web: "Website",
};

export class TemplateGallery extends Component {
    static template = "eh_board.TemplateGallery";
    static components = { Dialog };
    static props = {
        dashboardId: { type: [Number, { value: null }], optional: true },
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ templates: [], loading: true });
        this._ids = this.props.dashboardId ? [this.props.dashboardId] : [];
        onWillStart(async () => {
            this.state.templates = await this.orm.call(
                "eh.board.dashboard", "get_templates", [this._ids]);
            this.state.loading = false;
        });
    }

    categoryLabel(key) {
        return CATEGORY_LABELS[key] || key;
    }

    async use(t) {
        if (!t.available) return;
        const action = await this.orm.call(
            "eh.board.dashboard", "apply_template", [this._ids, t.id]);
        this.props.close();
        if (action && action.tag) {
            this.action.doAction(action);
        } else if (action && action.error) {
            this.notification.add(action.error, { type: "warning" });
        }
    }
}
