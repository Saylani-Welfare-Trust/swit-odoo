/** @odoo-module */
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

    toggleSelection() {
        if (!this.canSelectRecord) {
            return;
        }
        const value = !this.selectAll;
        for (const record of this.props.list.records) {
            record.toggleSelection(value);
        }
    }

    toggleRecordSelection(record) {
        if (!this.canSelectRecord) {
            return;
        }
        record.toggleSelection();
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
