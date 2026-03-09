"use client";

import { useCallback, useRef, useState } from "react";

interface FileUploadProps {
  onUpload: (file: File) => void;
}

export default function FileUpload({ onUpload }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      if (file.name.toLowerCase().endsWith(".pdf")) {
        onUpload(file);
      } else {
        alert("Please upload a PDF file.");
      }
    },
    [onUpload]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleClick = () => inputRef.current?.click();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div
      onClick={handleClick}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`
        relative cursor-pointer rounded-xl border-2 border-dashed p-16
        transition-all duration-200 ease-in-out
        flex flex-col items-center justify-center gap-4
        ${
          isDragging
            ? "border-blue-500 bg-blue-500/5"
            : "border-gray-700 bg-gray-900/50 hover:border-gray-500 hover:bg-gray-900"
        }
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        onChange={handleChange}
        className="hidden"
      />

      <svg
        className={`h-16 w-16 transition-colors ${
          isDragging ? "text-blue-400" : "text-gray-500"
        }`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m6.75 12-3-3m0 0-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
        />
      </svg>

      <div className="text-center">
        <p className="text-lg font-medium text-gray-200">
          {isDragging ? "Drop your PDF here" : "Drop your bank statement PDF here"}
        </p>
        <p className="mt-1 text-sm text-gray-500">or click to browse files</p>
      </div>

      <div className="mt-2 rounded-full bg-gray-800 px-4 py-1.5 text-xs text-gray-400">
        Supports Airwallex bank statements (.pdf)
      </div>
    </div>
  );
}
