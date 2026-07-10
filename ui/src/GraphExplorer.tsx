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

        const addNode = (id: string, kind?: string, intro?: string, del?: string, mod_count?: number) => {
          if (!nodes.has(id)) {
            newElements.push({ 
              data: { 
                id, 
                label: id, 
                kind,
                introduced_in: intro,
                deleted_in: del,
                modification_count: mod_count || 0
              } 
            });
            nodes.add(id);
          }
        };

        const getModCount = (fqn: string, symbols: any[]) => {
            const sym = symbols.find(s => s.fqn === fqn);
            return sym ? (sym.modified_in?.length || 0) : 0;
        };

        const allSyms = await fetchResource('get_symbols');

        calls.forEach((call: any) => {
          addNode(call.from, undefined, call.introduced_in, call.deleted_in, getModCount(call.from, allSyms));
          addNode(call.to, undefined, call.introduced_in, call.deleted_in, getModCount(call.to, allSyms));
          newElements.push({
            data: { 
              source: call.from, 
              target: call.to, 
              label: 'calls',
              introduced_in: call.introduced_in,
              deleted_in: call.deleted_in
            }
          });
        });

        imports.forEach((imp: any) => {
          addNode(imp.from, undefined, imp.introduced_in, imp.deleted_in);
          addNode(imp.to, 'external', imp.introduced_in, imp.deleted_in);
          newElements.push({
            data: { 
              source: imp.from, 
              target: imp.to, 
              label: 'imports', 
              type: 'IMPORTS_FROM',
              introduced_in: imp.introduced_in,
              deleted_in: imp.deleted_in
            }
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
            'transition-property': 'opacity, background-color',
            'transition-duration': '0.5s'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#ccc',
            'target-arrow-color': '#ccc',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'transition-property': 'opacity, line-color',
            'transition-duration': '0.5s'
          }
        },
        {
          selector: `[introduced_in = "${currentSha}"]`,
          style: {
            'background-color': '#3b82f6',
            'line-color': '#3b82f6',
            'target-arrow-color': '#3b82f6',
            'opacity': 1
          }
        },
        {
          selector: `[deleted_in = "${currentSha}"]`,
          style: {
            'background-color': '#ef4444',
            'line-color': '#ef4444',
            'target-arrow-color': '#ef4444',
            'opacity': 0
          }
        },
        {
          selector: 'node[modification_count > 0]',
          style: {
            'border-width': 2,
            'border-color': '#f59e0b',
          }
        },
        {
          selector: 'node[modification_count > 5]',
          style: {
            'background-color': '#f97316',
          }
        },
        {
          selector: 'node[modification_count > 10]',
          style: {
            'background-color': '#dc2626',
            'border-color': '#7f1d1d',
          }
        }
      ]}
    />
  );
};

export default GraphExplorer;
