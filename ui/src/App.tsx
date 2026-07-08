import { useWorkspaceStore } from './store/workspaceStore';
import { GitBranch, Share2, MessageSquare } from 'lucide-react';

function App() {
  const { currentBranch, currentSha } = useWorkspaceStore();

  return (
    <div className="flex h-screen w-full bg-gray-900 text-white overflow-hidden">
      {/* Left Panel: Git & File Tree */}
      <div className="w-64 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700 flex items-center gap-2">
          <GitBranch size={18} />
          <span className="font-semibold">History & Branch</span>
        </div>
        <div className="flex-1 p-4 overflow-y-auto">
          <div className="text-sm text-gray-400 mb-2">Current Branch: {currentBranch || 'N/A'}</div>
          <div className="text-xs text-gray-500 truncate">SHA: {currentSha || 'N/A'}</div>
          {/* Mock history rail */}
          <div className="mt-4 space-y-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="p-2 bg-gray-800 rounded text-xs cursor-pointer hover:bg-gray-700">
                Commit {i} ...
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Center Panel: Graph Visualization */}
      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b border-gray-700 flex items-center gap-2">
          <Share2 size={18} />
          <span className="font-semibold">Graph Explorer</span>
        </div>
        <div className="flex-1 relative bg-black flex items-center justify-center">
          <span className="text-gray-600 italic">Graph View Placeholder</span>
          {/* Future Cytoscape/Sigma.js integration */}
        </div>
      </div>

      {/* Right Panel: MCP Chat */}
      <div className="w-80 border-l border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700 flex items-center gap-2">
          <MessageSquare size={18} />
          <span className="font-semibold">MCP Chat</span>
        </div>
        <div className="flex-1 p-4 overflow-y-auto space-y-4">
           <div className="p-2 bg-gray-800 rounded text-sm">
             How can I help you analyze the codebase?
           </div>
        </div>
        <div className="p-4 border-t border-gray-700">
          <input 
            type="text" 
            placeholder="Ask MCP..." 
            className="w-full bg-gray-800 border border-gray-600 rounded p-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>
    </div>
  );
}

export default App;
