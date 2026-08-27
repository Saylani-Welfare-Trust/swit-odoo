/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * Deterministic tour for the tabbed, multi-measure builder: open a widget's
 * Configure and walk the Data / Display / Actions tabs, asserting the live
 * preview, multi-measure control, the DOMAIN widget, and display + action
 * options all render. Immune to SPA-navigation flakiness. */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("eh_board_builder_tour", {
    url: "/web#action=eh_board.action_eh_board_open",
    steps: () => [
        { trigger: ".eh_board_app .eh_board_widget", run: () => {} },
        { trigger: ".eh_board_header .eh_board_btn:contains(Edit)", run: "click" },
        {
            trigger: ".eh_board_widget[data-item-type=bar] button[title=Configure]",
            run: "click",
        },
        // full-screen editor open, in edit mode, with a live preview
        { trigger: ".eh_board_editor .eh_board_editor_head", run: () => {} },
        {
            trigger: ".eh_board_editor .eh_board_model_picker .o-autocomplete--input",
            run() {
                const picker = document.querySelector(".eh_board_editor .eh_board_model_picker");
                const inputs = picker.querySelectorAll("input");
                if (inputs.length !== 1 || !inputs[0].value.includes("res.partner")) {
                    throw new Error("model picker must be one autocomplete showing technical model");
                }
                if (picker.querySelector("select")) {
                    throw new Error("model picker must not render a duplicate select");
                }
            },
        },
        { trigger: ".eh_board_ed_preview .eh_board_widget", run: () => {} },
        // DATA tab: multi-measure (with per-measure format) + sort/limit + domain
        { trigger: ".eh_board_tabpane .eh_board_addbtn", run: () => {} },
        { trigger: ".eh_board_measure_row .eh_board_mfmt", run: () => {} },
        { trigger: ".eh_board_tabpane .eh_board_flabel:contains(Sort)", run: () => {} },
        { trigger: ".eh_board_tabpane .eh_board_flabel:contains(Row limit)", run: () => {} },
        // compact domain: a live match-count summary + an Edit-domain toggle that
        // reveals the full selector.
        { trigger: ".eh_board_domain_summary .eh_board_domain_count", run: () => {} },
        { trigger: ".eh_board_domain_edit", run: "click" },
        { trigger: ".eh_board_domain_wrap .o_domain_selector", run: () => {} },
        // DISPLAY tab
        { trigger: ".eh_board_tabs .eh_board_tab:contains(Display)", run: "click" },
        { trigger: ".eh_board_tabpane .eh_board_flabel:contains(Value format)", run: () => {} },
        { trigger: ".eh_board_tabpane .eh_board_toggle:contains(Legend)", run: () => {} },
        // ADVANCED tab: running total / fill gaps / group others
        { trigger: ".eh_board_tabs .eh_board_tab:contains(Advanced)", run: "click" },
        { trigger: ".eh_board_advrow .eh_board_toggle:contains(Running total)", run: () => {} },
        { trigger: ".eh_board_advrow .eh_board_toggle:contains(Others)", run: () => {} },
        // ACTIONS tab
        { trigger: ".eh_board_tabs .eh_board_tab:contains(Actions)", run: "click" },
        {
            trigger: ".eh_board_tabpane .eh_board_hint",
            run: () => {},
        },
    ],
});
