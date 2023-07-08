/** @odoo-module **/
const { xml, Component } = owl;
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useRPC } from "@web/core/hooks/useRPC";


export class FileDropWidget extends Component {
    setup() {
        super.setup();
        this.rpc = useRPC();
    }

    _onDrop(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.dataTransfer) {
            const { files } = ev.dataTransfer;
            [...files].forEach(file => {
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const { result } = e.target;
                    const base64Data = result.split(",")[1];
                    const recordIds = this.props.record.resIds;
                    await this.rpc({
                        route: "/web/dataset/call_kw",
                        params: {
                            model: 'product.import',
                            method: 'write',
                            args: [recordIds, { image_upload: base64Data }],
                        },
                    });

                };
                reader.readAsDataURL(file);
            });
        } else {
            console.error("dataTransfer is not available");
        }
    }

    _onDragEnter(ev) {
        ev.preventDefault();
        ev.target.classList.add('drag-over');
    }

    _onDragLeave(ev) {
        ev.preventDefault();
        ev.target.classList.remove('drag-over');
    }


}

FileDropWidget.template = xml`
<div class="o_field_file_drop" t-on-drop="_onDrop" t-on-dragover.prevent="" t-on-dragenter="_onDragEnter" t-on-dragleave="_onDragLeave" t-att-allowDrop="true">
    Drop files here...
</div>`;

FileDropWidget.props = standardFieldProps;

// Add the field to the correct category
registry.category("fields").add("file_drop", FileDropWidget);
