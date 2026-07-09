import { useEffect, useState } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import { useWorkspaceStore } from './store/workspaceStore';

const GraphExplorer = () => {
  const { currentSha } = useWorkspaceStore();
  const [elements, setElements] = useState<any[]>([]);

  useEffect(() => {
    const fetchGraphData = async () => {
      if (!currentSha) return;

      try {
        // Fetch calls for the current commit
        const fetchResource = async (rule: string) => {
          const response = await fetch('http://localhost:8000/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              rule: rule,
              commit_sha: currentSha
            })
          });
          const data = await response.json();
          return data.result || [];
        };

        const calls = await fetchResource('query_call_graph');
        const imports = await fetchResource('query_cross_repo_imports');

        const newElements: any[] = [];
        const nodes = new Set<string>();

        const addNode = (id: string, kind?: string) => {
          if (!nodes.has(id)) {
            newElements.push({ data: { id, label: id, kind } });
            nodes.add(id);
          }
        };

        calls.forEach((call: any) => {
          addNode(call.from);
          addNode(call.to);
          newElements.push({
            data: { source: call.from, target: call.to, label: 'calls' }
          });
        });

        imports.forEach((imp: any) => {
          addNode(imp.from);
          addNode(imp.to, 'external');
          newElements.push({
            data: { source: imp.from, target: imp.to, label: 'imports', type: 'IMPORTS_FROM' }
          });
        });

        // If no calls, maybe show symbols as nodes
        if (newElements.length === 0) {
            // Placeholder: fetch symbols
            newElements.push({ data: { id: 'Empty', label: 'No calls found for this commit' } });
        }

        setElements(newElements);
      } catch (error) {
        console.error('Error fetching graph data:', error);
      }
    };

    fetchGraphData();
  }, [currentSha]);

  return (
    <CytoscapeComponent
      elements={elements}
      style={{ width: '100%', height: '100%' }}
      layout={{ name: 'cose' }}
      stylesheet={[
        {
          selector: 'node',
          style: {
            'background-color': '#666',
            'label': 'data(label)',
            'color': '#fff',
            'font-size': '10px',
            'text-valign': 'center',
            'text-halign': 'center',
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#ccc',
            'target-arrow-color': '#ccc',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier'
          }
        }
      ]}
    />
  );
};

export default GraphExplorer;
