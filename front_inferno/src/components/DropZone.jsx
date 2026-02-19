import { Component } from "inferno";
import { IconUpload, IconSpinner } from "./Icons";

export default class DropZone extends Component {
  constructor(props) {
    super(props);
    this.state = { dragOver: false };
  }

  onDrop(e) {
    e.preventDefault();
    this.setState({ dragOver: false });
    const files = Array.from(e.dataTransfer.files);
    if (files.length && this.props.onFiles) this.props.onFiles(files);
  }

  render() {
    const { accept = ".xlsx,.xls,.pdf,.docx,.csv,.txt,.yaml,.yml", label, uploading, children } = this.props;
    const { dragOver } = this.state;

    return (
      <div
        class={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200 ${
          dragOver
            ? "border-indigo-500 bg-indigo-50/50 shadow-lg shadow-indigo-100/50"
            : uploading
              ? "border-indigo-300 bg-indigo-50/30"
              : "border-gray-300/80 bg-gray-50/50 hover:border-indigo-300 hover:bg-indigo-50/30"
        } ${dragOver ? "scale-[1.01]" : ""}`}
        style={dragOver ? { animation: "pulse-border 1.5s ease-in-out infinite" } : {}}
        onDragOver={(e) => { e.preventDefault(); this.setState({ dragOver: true }); }}
        onDragLeave={() => this.setState({ dragOver: false })}
        onDrop={(e) => this.onDrop(e)}
        onClick={() => this._input && this._input.click()}
      >
        <input
          ref={(el) => (this._input = el)}
          type="file"
          class="hidden"
          accept={accept}
          multiple
          onChange={(e) => {
            const files = Array.from(e.target.files);
            if (files.length && this.props.onFiles) this.props.onFiles(files);
          }}
        />
        {children || (
          <div class="flex flex-col items-center gap-3">
            <div class={`w-12 h-12 rounded-xl flex items-center justify-center transition-all ${dragOver ? "gradient-primary text-white scale-110" : uploading ? "bg-indigo-100 text-indigo-500" : "bg-gray-100 text-gray-400 group-hover:bg-indigo-100 group-hover:text-indigo-500"}`}>
              {uploading ? <IconSpinner size={24} /> : <IconUpload size={24} class={dragOver ? "animate-bounce" : ""} />}
            </div>
            <div>
              <p class="text-gray-700 font-medium text-sm">
                {uploading ? "Upload en cours..." : label || "Glissez vos fichiers ici ou cliquez"}
              </p>
              {!uploading && (
                <p class="text-xs text-gray-400 mt-1">
                  {accept.split(",").map((a) => a.trim().replace(".", "").toUpperCase()).join(", ")}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }
}
