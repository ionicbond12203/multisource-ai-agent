import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { KnowledgeFile } from "../types";
import { KnowledgeFileRow } from "./knowledge-file-row";
import { UploadDropzone } from "./upload-dropzone";

interface KnowledgeSidebarProps {
  files: KnowledgeFile[];
  onNewChat: () => void;
  onUpload: (files: File[]) => void;
  onToggleFile: (fileId: string) => void;
  onRemoveFile: (fileId: string) => void;
  onRunOcr: (fileId: string) => void;
}

export function KnowledgeSidebar({
  files,
  onNewChat,
  onUpload,
  onToggleFile,
  onRemoveFile,
  onRunOcr,
}: KnowledgeSidebarProps) {
  const totalChunks = files.reduce(
    (sum, file) => sum + (file.status.kind === "ready" ? file.status.chunks : 0),
    0,
  );

  return (
    <aside
      aria-label="Knowledge base"
      className="flex h-full flex-col gap-5 border-line bg-subtle p-4 xl:border-r"
    >
      <Button onClick={onNewChat} className="justify-center">
        <Plus aria-hidden="true" className="size-4" />
        New chat
      </Button>

      <section aria-labelledby="kb-heading" className="flex flex-col gap-2">
        <div>
          <h2 id="kb-heading" className="text-xs font-semibold tracking-wider text-ink-muted uppercase">
            Knowledge base
          </h2>
          <p className="text-xs text-ink-faint">
            {files.length} {files.length === 1 ? "file" : "files"} · {totalChunks} chunks indexed
          </p>
        </div>

        {files.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {files.map((file) => (
              <KnowledgeFileRow
                key={file.id}
                file={file}
                onToggle={onToggleFile}
                onRemove={onRemoveFile}
                onRunOcr={onRunOcr}
              />
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-ink-muted">Upload a document to start asking questions about it.</p>
        )}

        <UploadDropzone onFiles={onUpload} />
      </section>
    </aside>
  );
}
