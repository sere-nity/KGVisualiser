"use client";
import { useRef, useState } from "react";
import dynamic from "next/dynamic";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export default function Home() {
  // Legacy CSV upload (currently not in use)
  // const fileInputRef = useRef<HTMLInputElement>(null);
  // const [message, setMessage] = useState("");
  // const [loading, setLoading] = useState(false);
  // const handleCsvUpload = async (e: React.FormEvent) => { ... }

  // PDF upload state and handler
  const pdfInputRef = useRef<HTMLInputElement>(null);
  const [pdfMessage, setPdfMessage] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [uploadId, setUploadId] = useState<number | null>(null);

  // Chat state and handler
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<Array<{ question: string, answer: string }>>([]);

  // Handle PDF upload and set uploadId for chat context
  const handlePdfUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pdfInputRef.current?.files?.[0]) return;
    setPdfLoading(true);
    const formData = new FormData();
    formData.append("file", pdfInputRef.current.files[0]);
    try {
      const res = await fetch("http://localhost:8000/upload-pdf", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setPdfMessage(data.message || "PDF upload complete");
      setUploadId(data.upload_id); // Set uploadId from PDF upload
    } catch (error) {
      setPdfMessage("PDF upload failed. Please try again.");
    } finally {
      setPdfLoading(false);
    }
  };

  // Handle chat with PDF context
  const handlePdfChat = async () => {
    if (!question.trim()) return;
    setChatLoading(true);
    try {
      const res = await fetch("http://localhost:8000/chat-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, upload_id: uploadId }),
      });
      const data = await res.json();
      const newAnswer = data.answer;
      setAnswer(newAnswer);
      setChatHistory(prev => [...prev, { question, answer: newAnswer }]);
      setQuestion("");
    } catch (error) {
      const errorMessage = "Failed to get answer. Please try again.";
      setAnswer(errorMessage);
      setChatHistory(prev => [...prev, { question, answer: errorMessage }]);
      setQuestion("");
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <main className="flex h-screen bg-gray-50">
      {/* Left: Knowledge Graph Placeholder */}
      <div className="flex-1 flex items-center justify-center bg-gray-100 border-r-2 border-gray-200">
        {/* Future: Knowledge graph/mindmap visualization goes here */}
      </div>

      {/* Right: Chatbot Panel */}
      <div className="w-[600px] flex flex-col h-full bg-white shadow-xl">
        {/* PDF Upload at the top */}
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800 mb-2">Upload PDF</h2>
          <form onSubmit={handlePdfUpload} className="flex gap-2 items-center mb-2">
            <input
              type="file"
              accept=".pdf"
              ref={pdfInputRef}
              required
              className="block flex-1 text-sm text-gray-700 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={pdfLoading}
              className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline transition-colors duration-200"
            >
              {pdfLoading ? "Uploading..." : "Upload PDF"}
            </button>
          </form>
          {pdfMessage && (
            <div className="mt-2 p-2 bg-purple-50 border border-purple-200 rounded-lg">
              <p className="text-sm text-purple-700">{pdfMessage}</p>
            </div>
          )}
          {/*
            Legacy CSV Upload UI (currently disabled for project pivot)
            Uncomment and update if you want to support CSV uploads again.
          */}
          {/* ...CSV upload code here... */}
        </div>

        {/* Chat area for PDF context */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatHistory.map((chat, index) => (
              <div key={index} className="space-y-2">
                <div className="bg-blue-100 p-3 rounded-lg max-w-xs ml-auto">
                  <p className="text-sm font-medium text-blue-800">You:</p>
                  <p className="text-blue-700">{chat.question}</p>
                </div>
                <div className="bg-gray-100 p-3 rounded-lg max-w-xs">
                  <p className="text-sm font-medium text-gray-800">Assistant:</p>
                  <p className="text-gray-700">{chat.answer}</p>
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="bg-gray-100 p-3 rounded-lg max-w-xs">
                <p className="text-sm font-medium text-gray-800">Assistant:</p>
                <p className="text-gray-700">Thinking...</p>
              </div>
            )}
          </div>
          {/* Chat Input for PDF context */}
          <div className="bg-white border-t p-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={uploadId ? "Ask a question about your PDF..." : "Upload a PDF file first to ask questions..."}
                disabled={!uploadId}
                className="flex-1 p-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 text-gray-900"
                onKeyPress={(e) => e.key === 'Enter' && uploadId && handlePdfChat()}
              />
              <button
                onClick={handlePdfChat}
                disabled={chatLoading || !question.trim() || !uploadId}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline transition-colors duration-200"
              >
                {chatLoading ? "..." : "Send"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}