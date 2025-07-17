"use client";
import { useRef, useState } from "react";

export default function Home() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fileInputRef.current?.files?.[0]) return;

    const formData = new FormData();
    formData.append("file", fileInputRef.current.files[0]);

    const res = await fetch("http://localhost:8000/upload-csv", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    setMessage(data.message || "Upload complete");
  };

  return (
    <main className="flex flex-col items-center justify-center min-h-screen bg-gray-50 p-8">
      <form onSubmit={handleSubmit} className="bg-white shadow-md rounded px-8 pt-6 pb-8 mb-4 flex flex-col items-center gap-4 w-full max-w-md">
        <input
          type="file"
          accept=".csv"
          ref={fileInputRef}
          required
          className="block w-full text-sm text-gray-700 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <button
          type="submit"
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline transition-colors duration-200"
        >
          Upload CSV
        </button>
      </form>
      {message && (
        <p className="mt-2 text-center text-green-600 font-medium">{message}</p>
      )}
    </main>
  );
}