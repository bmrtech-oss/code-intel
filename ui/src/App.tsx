import { useWorkspaceStore } from './store/workspaceStore';
import { GitBranch, Share2, MessageSquare, Clock } from 'lucide-react';
import GraphExplorer from './GraphExplorer';

function App() {
  const { currentBranch, currentSha, ancestors, allCommits, setCurrentSha } = useWorkspaceStore();

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const index = parseInt(e.target.value);
    const reversed = [...allCommits].reverse();
    setCurrentSha(reversed[index]);
  };

  const currentIndex = [...allCommits].reverse().indexOf(currentSha);

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
          {/* History rail */}
          <div className="mt-4 space-y-2">
            {ancestors.map(sha => (
              <div 
                key={sha} 
                onClick={() => setCurrentSha(sha)}
                className={`p-2 rounded text-xs cursor-pointer hover:bg-gray-700 ${currentSha === sha ? 'bg-blue-600' : 'bg-gray-800'}`}
              >
                {sha}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Center Panel: Graph Visualization */}
      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Share2 size={18} />
            <span className="font-semibold">Graph Explorer</span>
          </div>
          
          {/* Timeline Scrubber */}
          <div className="flex items-center gap-4 bg-gray-800 px-4 py-2 rounded-full border border-gray-600">
            <Clock size={16} className="text-blue-400" />
            <input 
              type="range" 
              min="0" 
              max={allCommits.length - 1} 
              value={currentIndex >= 0 ? currentIndex : 0}
              onChange={handleSliderChange}
              className="w-48 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <span className="text-xs font-mono text-blue-300 w-12 text-center">
              {currentSha.substring(0, 7)}
            </span>
          </div>
        </div>
        <div className="flex-1 relative bg-black">
          <GraphExplorer />
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
