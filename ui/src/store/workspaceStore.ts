import { create } from 'zustand';

interface WorkspaceState {
  currentBranch: string;
  currentSha: string;
  ancestors: string[];
  recentCommits: string[];
  setWorkspace: (branch: string, sha: string, ancestors: string[]) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  currentBranch: '',
  currentSha: '',
  ancestors: [],
  recentCommits: [],
  setWorkspace: (branch, sha, ancestors) => 
    set((state) => {
        const newRecent = [sha, ...state.recentCommits.filter(s => s !== sha)].slice(0, 5);
        return {
            currentBranch: branch,
            currentSha: sha,
            ancestors: ancestors,
            recentCommits: newRecent
        };
    }),
}));
