/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { RecurringOrderRow } from "../recurring_order_row/recurring_order_row";
import { useService } from "@web/core/utils/hooks";


export class RecurringOrderList extends Component {
    static components = { RecurringOrderRow };
    static template = "pos_enhancement.RecurringOrderList";

    setup() {
        this.ui = useState(useService("ui"));
        this.state = useState({ highlightedOrder: this.props.initHighlightedOrder || null });
    }
    get highlightedOrder() {
        return this.state.highlightedOrder;
    }
    _onClickOrder(order) {
        this.state.highlightedOrder = order;
    }
}
