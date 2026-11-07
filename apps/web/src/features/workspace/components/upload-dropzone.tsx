"use client";

import { Upload } from "lucide-react";
import { useId, useState, type DragEvent } from "react";
import { siteConfig } from "@/config/site";
import { formatBytes, cn } from "@/lib/utils";

interface UploadDropzoneProps {
  onFiles: (files: File[]) => void;
}

/** Drag-and-drop target that also works as a regular file picker (keyboard and screen-reader friendly). */
export function UploadDropzone({ onFiles }: UploadDropzoneProps) {
  const inputId = useId();
  const [isDragging, setIsDragging] = useState(false);

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (event.dataTransfer.files.length > 0) onFiles([...event.dataTransfer.files]);
  }

  return (
    <label
      htmlFor={inputId}
      onDragOver={(event) => {
        event.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "flex cursor-pointer flex-col items-center gap-0.5 rounded-xl border-[1.5px] border-dashed p-3.5 text-center text-[13px] text-ink-muted transition-colors",
        isDragging ? "border-accent bg-accent-tint" : "border-line-stronger hover:border-ink-faint",
      )}
    >
      <Upload aria-hidden="true" className="mb-1 size-5" />
      <span>
        Drop files or <span className="font-medium text-accent underline">browse</span>
      </span>
      <span className="text-xs text-ink-faint">
        {siteConfig.upload.acceptedExtensions.map((ext) => ext.slice(1).toUpperCase()).join(", ")} · up to{" "}
        {formatBytes(siteConfig.upload.maxFileSizeBytes)}
      </span>
      <input
        id={inputId}
        type="file"
        multiple
        accept={siteConfig.upload.acceptedExtensions.join(",")}
        className="sr-only"
        onChange={(event) => {
          if (event.target.files) onFiles([...event.target.files]);
          event.target.value = ""; // allow picking the same file again
        }}
      />
    </label>
  );
}
