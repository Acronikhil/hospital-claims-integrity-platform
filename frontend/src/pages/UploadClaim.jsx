import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadClaimDocuments } from "../api.js";

const MAX_FILES = 10;

export default function UploadClaim() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const addFiles = (candidates) => {
    if (!candidates || candidates.length === 0) return;

    const incoming = Array.from(candidates);
    const nonPdf = incoming.find((f) => f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf"));
    if (nonPdf) {
      setError(`'${nonPdf.name}' is not a PDF.`);
      return;
    }

    setError(null);
    setFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name + f.size));
      const merged = [...prev, ...incoming.filter((f) => !existingNames.has(f.name + f.size))];
      if (merged.length > MAX_FILES) {
        setError(`You can attach at most ${MAX_FILES} documents per claim.`);
        return merged.slice(0, MAX_FILES);
      }
      return merged;
    });
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    addFiles(e.dataTransfer.files);
  };

  const handleSubmit = async () => {
    if (files.length === 0) {
      setError("Choose at least one claim document (PDF) first.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const report = await uploadClaimDocuments(files);
      navigate(`/claims/${report.claimId}`);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to process these documents.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Upload Claim</h1>
      </div>

      <p className="muted upload-intro">
        Upload one or more documents for this claim - the final bill, pre-authorization form,
        discharge summary, prescriptions, investigation reports. The Document Intelligence Agent
        reads all of them together - including scanned/photographed pages - and reconciles patient,
        hospital, procedure and bill item details into a single claim record. The claim is then
        written into the knowledge graph and investigated by the Tariff and Duplicate Billing
        agents.
      </p>

      <div
        className={`dropzone ${dragActive ? "dropzone-active" : ""} ${files.length ? "dropzone-filled" : ""}`}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          multiple
          hidden
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        {files.length > 0 ? (
          <div className="file-list" onClick={(e) => e.stopPropagation()}>
            {files.map((file, idx) => (
              <div className="file-list-row" key={file.name + file.size}>
                <span className="dropzone-icon-small">📄</span>
                <span className="file-list-name">{file.name}</span>
                <span className="muted">{(file.size / 1024).toFixed(0)} KB</span>
                <button type="button" className="remove-btn" onClick={() => removeFile(idx)}>
                  ✕
                </button>
              </div>
            ))}
            <button type="button" className="add-item-btn" onClick={() => fileInputRef.current?.click()}>
              + Add another document
            </button>
          </div>
        ) : (
          <>
            <div className="dropzone-icon">⬆</div>
            <div className="dropzone-title">Drop claim document PDFs here, or click to browse</div>
            <div className="muted">PDF only, up to 20 MB each, {MAX_FILES} documents max</div>
          </>
        )}
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="form-actions">
        <button className="primary-btn" onClick={handleSubmit} disabled={uploading || files.length === 0}>
          {uploading ? "Investigating Claim…" : "Investigate Claim"}
        </button>
      </div>
    </div>
  );
}
