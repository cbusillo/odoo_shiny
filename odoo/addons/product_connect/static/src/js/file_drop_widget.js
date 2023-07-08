/** @odoo-module **/
const { xml, Component } = owl;
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class FileDropWidget extends Component {
    setup() {
        super.setup();
    }

    _onDrop(ev) {
        ev.target.classList.remove('drag-over');
        ev.target.textContent = "Drop files here...";
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.dataTransfer) {
            const { files } = ev.dataTransfer;
            [...files].forEach(file => {
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const { result } = e.target;
                    const splitResult = result.split(",");
                    if (splitResult.length > 1) {
                        const base64Data = splitResult[1];
                        this.props.update(base64Data);
                    } else {
                        console.error("Unable to split result into data and mime type");
                    }
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
        ev.target.textContent = "Release to upload file";
    }

    _onDragLeave(ev) {
        ev.preventDefault();
        ev.target.classList.remove('drag-over');
        ev.target.textContent = "Drop files here...";
    }
    _onDragOver(ev) {
        ev.preventDefault();
    }


}

FileDropWidget.template = xml`
<div class="o_field_file_drop" t-on-drop="_onDrop" t-on-dragover="_onDragOver" t-on-dragenter="_onDragEnter" t-on-dragleave="_onDragLeave" t-att-allowDrop="true">
    Drop files here...
</div>`;

FileDropWidget.props = standardFieldProps;

// Add the field to the correct category
registry.category("fields").add("file_drop", FileDropWidget);

