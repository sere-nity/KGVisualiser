"use client";
import { useRef, useState } from "react";
import dynamic from "next/dynamic";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export default function Home() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState("");
  const [uploadId, setUploadId] = useState<number | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<Array<{question: string, answer: string}>>([]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fileInputRef.current?.files?.[0]) return;

    setLoading(true);
    const formData = new FormData();
    formData.append("file", fileInputRef.current.files[0]);

    try {
      const res = await fetch("http://localhost:8000/upload-csv", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      setMessage(data.message || "Upload complete");
      setUploadId(data.upload_id);
    } catch (error) {
      setMessage("Upload failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleChat = async () => {
    if (!question.trim()) return;

    setChatLoading(true);
    try {
      const res = await fetch("http://localhost:8000/chat", {
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
      
      </div>

      {/* Right: Chatbot Panel */}
      <div className="w-[600px] flex flex-col h-full bg-white shadow-xl">
        {/* Upload at the top */}
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800 mb-2">Upload CSV Data</h2>
          <form onSubmit={handleSubmit} className="flex gap-2 items-center">
            <input
              type="file"
              accept=".csv"
              ref={fileInputRef}
              required
              className="block flex-1 text-sm text-gray-700 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline transition-colors duration-200"
            >
              {loading ? "Uploading..." : "Upload"}
            </button>
          </form>
          {message && (
            <div className="mt-2 p-2 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-700">{message}</p>
            </div>
          )}
          {uploadId && (
            <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-700">
                ✓ Data loaded (ID: {uploadId})
              </p>
            </div>
          )}
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatHistory.length === 0 && !uploadId && (
              <div className="text-center text-gray-500 mt-8">
                <p>Welcome! Upload a CSV file to start asking questions about your data.</p>
              </div>
            )}
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
          {/* Chat Input */}
          <div className="bg-white border-t p-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={uploadId ? "Ask a question about your data..." : "Upload a CSV file first to ask questions..."}
                disabled={!uploadId}
                className="flex-1 p-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                onKeyPress={(e) => e.key === 'Enter' && uploadId && handleChat()}
              />
              <button
                onClick={handleChat}
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