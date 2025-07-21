"use client";
import { useRef, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import CytoscapeComponent from "react-cytoscapejs";
import cytoscape from "cytoscape";
import coseBilkent from "cytoscape-cose-bilkent";
import {
  NODE_REPULSION,
  IDEAL_EDGE_LENGTH,
  EDGE_ELASTICITY,
  GRAPH_GRAVITY,
  LAYOUT_NUM_ITER,
  GRAPH_PADDING,
  TILING_PADDING_VERTICAL,
  TILING_PADDING_HORIZONTAL,
  GRAVITY_RANGE_COMPOUND,
  GRAVITY_COMPOUND,
  INITIAL_ENERGY_ON_INCREMENTAL,
  CLUSTER_COLORS
} from "./config";
cytoscape.use(coseBilkent);

type Triplet = { subject: string; relation: string; object: string; source_text?: string };

type CytoscapeElement = { data: { id?: string; label?: string; source?: string; target?: string; cluster_id?: number } };

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
  const [graphElements, setGraphElements] = useState<CytoscapeElement[]>([]);
  const [ragStats, setRagStats] = useState<{ queryTime?: number, tokenUsage?: any }>({});

  // Fetch knowledge graph triplets after PDF upload
  useEffect(() => {
    console.log("graphElements:", graphElements);
    if (uploadId) {
      fetch(`http://localhost:8000/graph/${uploadId}`)
        .then(res => res.json())
        .then((triplets: Triplet[]) => {
          // get node cluster ids
          fetch(`http://localhost:8000/graph/nodes/${uploadId}`)
            .then(res => res.json())
            // id of the node is the node name 
            .then((nodeClusterIds: {node_id: string, cluster_id: number}[]) => {
                const clusterMap = Object.fromEntries(nodeClusterIds.map(n => [n.node_id, n.cluster_id]));
                const cytoscapeNodes: CytoscapeElement[] = [];
                const edges: CytoscapeElement[] = [];
                const nodeSet = new Set();
                triplets.forEach(({ subject, relation: predicate, object }) => {
                  // nodeSet is used to avoid duplicate nodes (but visualisation handles this automatically anyway)
                  if (!nodeSet.has(subject)) {
                    cytoscapeNodes.push({ data: { id: subject, label: subject, cluster_id: clusterMap[subject] ?? 0 } });
                    nodeSet.add(subject);
                  }
                  if (!nodeSet.has(object)) {
                    cytoscapeNodes.push({ data: { id: object, label: object, cluster_id: clusterMap[object] ?? 0 } });
                    nodeSet.add(object);
                  }
                  edges.push({ data: { source: subject, target: object, label: predicate } });
                });
                setGraphElements([...cytoscapeNodes, ...edges]);
            }); 
        });
    }
  }, [uploadId]);

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
      setRagStats({ queryTime: data.query_time, tokenUsage: data.token_usage });
    } catch (error) {
      const errorMessage = "Failed to get answer. Please try again.";
      setAnswer(errorMessage);
      setChatHistory(prev => [...prev, { question, answer: errorMessage }]);
      setQuestion("");
      setRagStats({});
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <main className="flex h-screen bg-gray-50">
      {/* Left: Knowledge Graph Visualization + RAG Statistics */}
      <div className="flex-1 flex flex-col bg-gray-100 border-r-2 border-gray-200 h-full">
        <div className="flex-1 flex items-center justify-center">
          {uploadId && graphElements.length > 0 ? (
            <CytoscapeComponent
              elements={graphElements}
              style={{ width: "95%", height: "90%", background: "#fff" }}
              layout={{
                name: "cose-bilkent",
                nodeClusterAttribute: "cluster_id",
                animate: true,
                randomize: true,
                fit: true,
                padding: GRAPH_PADDING,
                nodeRepulsion: NODE_REPULSION,
                idealEdgeLength: IDEAL_EDGE_LENGTH,
                edgeElasticity: EDGE_ELASTICITY,
                gravity: GRAPH_GRAVITY,
                numIter: LAYOUT_NUM_ITER,
                tile: true,
                tilingPaddingVertical: TILING_PADDING_VERTICAL,
                tilingPaddingHorizontal: TILING_PADDING_HORIZONTAL,
                gravityRangeCompound: GRAVITY_RANGE_COMPOUND,
                gravityCompound: GRAVITY_COMPOUND,
                initialEnergyOnIncremental: INITIAL_ENERGY_ON_INCREMENTAL,
              }}
              stylesheet={[
                // One style per cluster
                ...CLUSTER_COLORS.map((color, idx) => ({
                  selector: `node[cluster_id = ${idx}]`,
                  style: { 'background-color': color }
                })),
                {
                  selector: 'node',
                  style: {
                    'label': 'data(label)',
                    'color': '#222',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': 16,
                    'width': 40,
                    'height': 40,
                  }
                },
                {
                  selector: 'edge',
                  style: {
                    'label': 'data(label)',
                    'curve-style': 'bezier',
                    'target-arrow-shape': 'triangle',
                    'width': 3,
                    'line-color': '#888',
                    'target-arrow-color': '#888',
                    'font-size': 14,
                    'color': '#222',
                    'text-background-color': '#fff',
                    'text-background-opacity': 1,
                    'text-background-padding': 6,
                    'text-border-color': '#fff',
                    'text-border-width': 1,
                    'text-border-opacity': 1,
                    'text-background-shape': 'roundrectangle',
                    'text-margin-y': -8,
                  }
                }
              ]}
            />
          ) : (
            <span className="text-gray-400 text-lg">Upload a PDF to see the knowledge graph.</span>
          )}
        </div>
        {/* RAG Statistics Section */}
        <div className="w-full bg-gray-200 p-6 flex flex-col items-center justify-center min-h-[200px] border-t border-gray-300">
          {ragStats.queryTime !== undefined ? (
            <>
              <span className="text-3xl font-bold text-gray-700 tracking-wide mb-2">Query Statistics</span>
              <div className="text-lg text-gray-800">Query Time: {ragStats.queryTime.toFixed(2)}s</div>
              {ragStats.tokenUsage && ragStats.tokenUsage.total_tokens !== undefined && (
                <div className="text-lg text-gray-800">Tokens Used: {ragStats.tokenUsage.total_tokens}</div>
              )}
            </>
          ) : (
            <span className="text-lg text-gray-500">No query made yet.</span>
          )}
        </div>
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
        {pdfLoading && (
          <div className="flex items-center gap-2 mt-2">
            <svg className="animate-spin h-6 w-6 text-purple-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
            </svg>
            <span className="text-purple-700">Processing PDF, please wait...</span>
          </div>
        )}
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