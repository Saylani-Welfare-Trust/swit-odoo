/** @odoo-module */
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ListRenderer } from "@web/views/list/list_renderer";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

/**
 * One2many lists (StaticList) have no selection API in Odoo 17, so the
 * renderer tracks selection through each record's `selected` flag only.
 */
export class SelectableListRenderer extends ListRenderer {
    get selectAll() {
        const records = this.props.list.records;
        return records.length > 0 && records.every((r) => r.selected);
    }

    // Editable lists: allow ticking while a row is in edition, the row is
    // left (and validated) first in toggleRecordSelection.
    get canSelectRecord() {
        return !this.props.list.model.useSampleModel;
    }

    async toggleSelection() {
        if (!this.canSelectRecord || !(await this.props.list.leaveEditMode())) {
            return;
        }
        const value = !this.selectAll;
        for (const record of this.props.list.records) {
            record.toggleSelection(value);
        }
    }

    async toggleRecordSelection(record) {
        if (!this.canSelectRecord || !(await this.props.list.leaveEditMode())) {
            return;
        }
        record.toggleSelection();
    }

    // Same as ListRenderer.onRowTouchStart, without `list.selection` which
    // StaticList does not provide.
    onRowTouchStart(record, ev) {
        if (this.props.list.records.some((r) => r.selected)) {
            ev.stopPropagation();
        }
        this.touchStartMs = Date.now();
        if (this.longTouchTimer === null) {
            this.longTouchTimer = browser.setTimeout(() => {
                this.toggleRecordSelection(record);
                this.resetLongTouchTimer();
            }, this.constructor.LONG_TOUCH_THRESHOLD);
        }
    }
}

export class SelectableX2ManyField extends X2ManyField {
    static template = "bn_advance_donation.SelectableX2ManyField";
    static components = { ...X2ManyField.components, ListRenderer: SelectableListRenderer };
    static props = {
        ...X2ManyField.props,
        printMethod: { type: String, optional: true },
        printLabel: { type: String, optional: true },
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    get rendererProps() {
        const props = super.rendererProps;
        if (this.props.viewMode === "list") {
            props.allowSelectors = true;
        }
        return props;
    }

    get selectedRecords() {
        return this.list.records.filter((r) => r.selected && r.resId);
    }

    async onPrintSelected() {
        const resIds = this.selectedRecords.map((r) => r.resId);
        if (!resIds.length) {
            return;
        }
        // Like form buttons: persist pending edits before printing from DB.
        if (!(await this.props.record.save())) {
            return;
        }
        const action = await this.orm.call(this.list.resModel, this.props.printMethod, [resIds]);
        await this.action.doAction(action);
    }
}

export const selectableX2ManyField = {
    ...x2ManyField,
    component: SelectableX2ManyField,
    extractProps: (fieldInfo, dynamicInfo) => ({
        ...x2ManyField.extractProps(fieldInfo, dynamicInfo),
        printMethod: fieldInfo.options.print_method,
        printLabel: fieldInfo.options.print_label,
    }),
};

registry.category("fields").add("one2many_selectable", selectableX2ManyField);
