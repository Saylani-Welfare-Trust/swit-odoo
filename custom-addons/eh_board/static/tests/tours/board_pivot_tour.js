/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * Deterministic tour: the pivot / cross-tab matrix widget renders as a real
 * HTML table with row headers, a heat-mapped body and a grand-total cell. */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("eh_board_pivot_tour", {
    url: "/web#action=eh_board.action_eh_board_open",
    steps: () => [
        { trigger: ".eh_board_app .eh_board_widget", run: () => {} },
        // the pivot widget mounted a real table
        { trigger: ".eh_board_widget[data-item-type=pivot] .eh_board_pivot_table", run: () => {} },
        // it has a pinned row header
        { trigger: ".eh_board_pivot_table .eh_board_pivot_rowhead", run: () => {} },
        // and a grand-total cell in the footer
        {
            trigger: ".eh_board_pivot_table .eh_board_pivot_foot .eh_board_pivot_grand",
            run: () => console.log("tour succeeded"),
        },
    ],
});
