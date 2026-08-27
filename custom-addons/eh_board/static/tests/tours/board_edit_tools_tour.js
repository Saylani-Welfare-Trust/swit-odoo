/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * Deterministic tour for the edit-mode tools: duplicate a widget and open the
 * in-canvas Add-filter dialog. */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("eh_board_edit_tools_tour", {
    url: "/web#action=eh_board.action_eh_board_open",
    steps: () => [
        { trigger: ".eh_board_app .eh_board_widget", run: () => {} },
        // presentation mode: Play opens a slideshow overlay with controls; step
        // once, then exit back to the board (header restored).
        { trigger: ".eh_board_playbtn", run: "click" },
        { trigger: ".eh_board_present .eh_board_present_ctrl", run: () => {} },
        { trigger: ".eh_board_present_slide .eh_board_widget", run: () => {} },
        { trigger: ".eh_board_present_btn.eh_board_present_play", run: "click" },
        { trigger: ".eh_board_present_ctrl .eh_board_present_exit", run: "click" },
        { trigger: ".eh_board_app:not(.o_kiosk) .eh_board_toolbar", run: () => {} },
        // the top-left main menu drawer
        { trigger: ".eh_board_menubtn", run: "click" },
        { trigger: ".eh_board_menu_drawer .eh_board_menu_item:contains(New dashboard)", run: () => {} },
        { trigger: ".eh_board_menu_drawer .eh_board_menu_item:contains(All Odoo apps)", run: () => {} },
        { trigger: ".eh_board_menubtn", run: "click" },
        { trigger: ".eh_board_header .eh_board_btn:contains(Edit)", run: "click" },
        // the drag grip must be the TOP element at its own centre (not hidden
        // behind the widget header) so it actually receives the drag pointerdown.
        {
            trigger: ".eh_board_grid.o_editing .eh_board_cell .eh_board_move_handle",
            run() {
                const h = document.querySelector(
                    ".eh_board_grid.o_editing .eh_board_cell .eh_board_move_handle");
                const r = h.getBoundingClientRect();
                const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                // The topmost element at the grip's centre must belong to a drag
                // grip (not the widget header) - else the pointerdown is swallowed.
                if (!top || !top.closest(".eh_board_move_handle")) {
                    throw new Error("drag grip is covered by " + (top && top.className));
                }
            },
        },
        // dashboard settings are reachable from the header and render fields
        { trigger: ".eh_board_btn[title='Dashboard settings']", run: "click" },
        { trigger: ".eh_board_settings .eh_board_settings_grid", run: () => {} },
        { trigger: ".eh_board_settings .eh_board_flabel:contains(Colour palette)", run: () => {} },
        { trigger: ".eh_board_settings .eh_board_flabel:contains(Opens with date range)", run: () => {} },
        // the searchable people picker renders (search box + an add option)
        { trigger: ".eh_board_settings .eh_board_userpick input", run: () => {} },
        { trigger: ".eh_board_settings .eh_board_userlist .eh_board_useropt", run: () => {} },
        { trigger: ".modal-footer .btn:contains(Cancel)", run: "click" },
        // duplicate the KPI widget
        {
            trigger: ".eh_board_widget[data-item-type=kpi] button[title=Duplicate]",
            run: "click",
        },
        { trigger: ".eh_board_widget_title:contains(copy)", run: () => {} },
        // Discard button is present in edit mode (safety net for non-technical users)
        { trigger: ".eh_board_header .eh_board_btn:contains(Discard)", run: () => {} },
        // Delete asks for confirmation instead of deleting on the spot
        { trigger: ".eh_board_widget[data-item-type=kpi] button[title=Remove]", run: "click" },
        { trigger: ".modal-body:contains(cannot be undone)", run: () => {} },
        { trigger: ".modal-footer .btn:contains(Keep it)", run: "click" },
        // still present after cancelling the delete
        { trigger: ".eh_board_widget[data-item-type=kpi]", run: () => {} },
        // export menu offers PDF / Excel / CSV / JSON
        { trigger: ".eh_board_export .eh_board_btn.o_icon", run: "click" },
        { trigger: ".eh_board_export_menu button:contains(PDF)", run: () => {} },
        { trigger: ".eh_board_export_menu button:contains(Excel workbook)", run: () => {} },
        { trigger: ".eh_board_export_menu button:contains(JSON spec)", run: () => {} },
        { trigger: ".eh_board_export .eh_board_btn.o_icon", run: "click" },
        // open the in-canvas Add-filter dialog
        { trigger: ".eh_board_header .eh_board_btn:contains(Filter)", run: "click" },
        {
            trigger: ".eh_board_addfilter",
            run: () => console.log("tour succeeded"),
        },
    ],
});
