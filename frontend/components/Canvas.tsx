"use client";

import "@xyflow/react/dist/style.css";

import {
  addEdge,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Connection,
  type Edge,
  type Node,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useState, type CSSProperties, type DragEvent, type PointerEvent as ReactPointerEvent } from "react";

import AgentNode from "./nodes/AgentNode";
import ApprovalReview from "./ApprovalReview";
import ChatPanel from "./ChatPanel";
import ControlCenterPanel from "./ControlCenterPanel";
import LibraryPanel from "./LibraryPanel";
import BuzzNode from "./nodes/BuzzNode";
import CoderNode from "./nodes/CoderNode";
import FileNode from "./nodes/FileNode";
import PlannerNode from "./nodes/PlannerNode";
import StartNode from "./nodes/StartNode";
import TaskNode from "./nodes/TaskNode";
import ToolNode from "./nodes/ToolNode";
import RuntimeNode from "./nodes/RuntimeNode";
import DecomposeNode from "./nodes/DecomposeNode";
import RunInspector from "./RunInspector";
import { ChatInputNode, ContextNode, MergeNode, PluginNode, ReviewNode, SplitNode } from "./nodes/WorkflowControlNodes";
import { NODE_META, nodeDefaults, persistedData, type NodeKind, type WorkspaceNodeData } from "./nodes/types";
import type { ApprovalPreview, LibraryResource } from "../lib/library-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const NODE_MIME = "application/x-mo-node-kind";
const RESOURCE_MIME = "application/x-mo-library-resource";

type CanvasNode = Node<WorkspaceNodeData, NodeKind>;
type RunStatus = "idle" | "saving" | "validating" | "running" | "complete" | "error";

type Health = {
  status: string;
  model_provider: string;
  nanbeige_model: string;
  nanbeige_ready: boolean;
  lfm_model: string;
  lfm_ready: boolean;
  minimax_model: string;
  ollama_model: string;
  buzz_on_path: boolean;
  configured_agents: string[];
};

type ProjectSummary = {
  id: string;
  name: string;
  updated_at?: string | null;
};

type ProjectResponse = ProjectSummary & {
  canvas_state: { nodes: CanvasNode[]; edges: Edge[] };
};

type RunLine = {
  id: string;
  kind: "system" | "node" | "error" | "complete";
  text: string;
};

type SseMessage = {
  event: string;
  data: Record<string, unknown>;
};

type PendingApproval = ApprovalPreview & (
  | { kind: "action"; resource: LibraryResource; arguments: Record<string, unknown> }
  | { kind: "graph" }
);

const LAYOUT_STORAGE_KEY = "mo-workspace-panel-layout-v1";
const DEFAULT_LEFT_PANEL = 320;
const DEFAULT_RIGHT_PANEL = 340;
const MIN_LEFT_PANEL = 240;
const MIN_RIGHT_PANEL = 280;
const MIN_CANVAS = 420;

const initialNodes: CanvasNode[] = [
  {
    id: "start-1",
    type: "start",
    position: { x: 120, y: 190 },
    data: nodeDefaults("start"),
  },
  {
    id: "coder-1",
    type: "coder",
    position: { x: 520, y: 150 },
    data: nodeDefaults("coder"),
  },
];

const initialEdges: Edge[] = [
  {
    id: "edge-start-coder",
    source: "start-1",
    target: "coder-1",
    animated: true,
  },
];

const nodeTypes = {
  start: StartNode,
  buzz: BuzzNode,
  planner: PlannerNode,
  coder: CoderNode,
  file: FileNode,
  task: TaskNode,
  agent: AgentNode,
  tool: ToolNode,
  runtime: RuntimeNode,
  review: ReviewNode,
  chat: ChatInputNode,
  split: SplitNode,
  merge: MergeNode,
  context: ContextNode,
  plugin: PluginNode,
  delegate: DecomposeNode,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNodeKind(value: unknown): value is NodeKind {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(nodeTypes, value);
}

function isProjectResponse(value: unknown): value is ProjectResponse {
  if (!isRecord(value) || typeof value.id !== "string" || typeof value.name !== "string") return false;
  const canvas = value.canvas_state;
  if (!isRecord(canvas) || !Array.isArray(canvas.nodes) || !Array.isArray(canvas.edges)) return false;
  const validNodes = canvas.nodes.every((node) => {
    if (!isRecord(node) || typeof node.id !== "string" || !isNodeKind(node.type)) return false;
    if (!isRecord(node.position) || typeof node.position.x !== "number" || typeof node.position.y !== "number") return false;
    return isRecord(node.data);
  });
  const validEdges = canvas.edges.every(
    (edge) => isRecord(edge) && typeof edge.id === "string" && typeof edge.source === "string" && typeof edge.target === "string",
  );
  return validNodes && validEdges;
}

function createNode(kind: NodeKind, position: { x: number; y: number }): CanvasNode {
  return {
    id: `${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    type: kind,
    position,
    data: nodeDefaults(kind),
  };
}

function serializedGraph(nodes: CanvasNode[], edges: Edge[]) {
  return {
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: node.position,
      data: persistedData(node.data),
    })),
    edges: edges.map((edge) => ({
      id: edge.id || `${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      label: typeof edge.label === "string" ? edge.label : "",
      priority: typeof edge.data?.priority === "number" ? edge.data.priority : 0,
      condition: isRecord(edge.data?.condition) ? edge.data.condition : {},
    })),
  };
}

function parseSseBlock(block: string): SseMessage | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  const data = dataLines.join("\n");
  if (!data) return null;
  try {
    return { event, data: JSON.parse(data) as Record<string, unknown> };
  } catch {
    return { event, data: { detail: data } };
  }
}

function displayError(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "The local workspace request failed.";
}

export default function Canvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasNode>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance<CanvasNode, Edge> | null>(null);
  const [projectName, setProjectName] = useState("Untitled local workflow");
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [inputText, setInputText] = useState("Describe the coding task for this workflow.");
  const [output, setOutput] = useState("");
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [notice, setNotice] = useState("Ready to compose a local workflow.");
  const [runLines, setRunLines] = useState<RunLine[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [approvalPolicy, setApprovalPolicy] = useState<"preflight" | "per_action" | "step_through">("per_action");
  const [leftPanelWidth, setLeftPanelWidth] = useState(DEFAULT_LEFT_PANEL);
  const [rightPanelWidth, setRightPanelWidth] = useState(DEFAULT_RIGHT_PANEL);
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [layoutHydrated, setLayoutHydrated] = useState(false);
  const [stackedLayout, setStackedLayout] = useState(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem(LAYOUT_STORAGE_KEY) ?? "null") as Record<string, unknown> | null;
      if (saved) {
        if (typeof saved.leftWidth === "number") setLeftPanelWidth(Math.min(600, Math.max(MIN_LEFT_PANEL, saved.leftWidth)));
        if (typeof saved.rightWidth === "number") setRightPanelWidth(Math.min(650, Math.max(MIN_RIGHT_PANEL, saved.rightWidth)));
        setLeftPanelCollapsed(saved.leftCollapsed === true);
        setRightPanelCollapsed(saved.rightCollapsed === true);
      }
    } catch { /* Invalid local layout falls back to defaults. */ }
    const media = window.matchMedia("(max-width: 880px)");
    const syncStacked = () => setStackedLayout(media.matches);
    syncStacked();
    media.addEventListener("change", syncStacked);
    setLayoutHydrated(true);
    return () => media.removeEventListener("change", syncStacked);
  }, []);

  useEffect(() => {
    if (!layoutHydrated) return;
    window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify({
      leftWidth: leftPanelWidth,
      rightWidth: rightPanelWidth,
      leftCollapsed: leftPanelCollapsed,
      rightCollapsed: rightPanelCollapsed,
    }));
  }, [layoutHydrated, leftPanelCollapsed, leftPanelWidth, rightPanelCollapsed, rightPanelWidth]);

  const resizePanel = useCallback((side: "left" | "right", requested: number) => {
    const viewport = window.innerWidth;
    const opposite = side === "left"
      ? (rightPanelCollapsed ? 36 : rightPanelWidth)
      : (leftPanelCollapsed ? 36 : leftPanelWidth);
    const minimum = side === "left" ? MIN_LEFT_PANEL : MIN_RIGHT_PANEL;
    const configuredMaximum = side === "left" ? 600 : 650;
    const availableMaximum = Math.max(minimum, viewport - opposite - MIN_CANVAS - 16);
    const next = Math.min(configuredMaximum, availableMaximum, Math.max(minimum, requested));
    if (side === "left") setLeftPanelWidth(next); else setRightPanelWidth(next);
  }, [leftPanelCollapsed, leftPanelWidth, rightPanelCollapsed, rightPanelWidth]);

  const beginPanelResize = useCallback((side: "left" | "right", event: ReactPointerEvent<HTMLDivElement>) => {
    if (stackedLayout) return;
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = side === "left" ? leftPanelWidth : rightPanelWidth;
    document.body.classList.add("panel-resizing");
    const move = (pointer: PointerEvent) => resizePanel(side, startWidth + (side === "left" ? pointer.clientX - startX : startX - pointer.clientX));
    const stop = () => {
      document.body.classList.remove("panel-resizing");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, { once: true });
  }, [leftPanelWidth, resizePanel, rightPanelWidth, stackedLayout]);

  const resizePanelByKeyboard = useCallback((side: "left" | "right", key: string) => {
    if (key !== "ArrowLeft" && key !== "ArrowRight") return;
    const current = side === "left" ? leftPanelWidth : rightPanelWidth;
    const direction = key === "ArrowRight" ? 1 : -1;
    resizePanel(side, current + (side === "left" ? direction : -direction) * 20);
  }, [leftPanelWidth, resizePanel, rightPanelWidth]);

  const resetPanelLayout = useCallback(() => {
    setLeftPanelWidth(DEFAULT_LEFT_PANEL);
    setRightPanelWidth(DEFAULT_RIGHT_PANEL);
    setLeftPanelCollapsed(false);
    setRightPanelCollapsed(false);
    setNotice("Workspace panel layout reset.");
  }, []);

  const updateNodeData = useCallback((id: string, patch: Record<string, unknown>) => {
    setNodes((current) =>
      current.map((node) => (node.id === id ? { ...node, data: { ...node.data, ...patch } } : node)),
    );
  }, [setNodes]);

  const bindNode = useCallback((node: CanvasNode): CanvasNode => {
    return {
      ...node,
      data: {
        ...node.data,
        onChange: (patch: Record<string, unknown>) => updateNodeData(node.id, patch),
      },
    };
  }, [updateNodeData]);

  useEffect(() => {
    setNodes((current) => current.map((node) => bindNode(node as CanvasNode)));
  }, [bindNode, setNodes]);

  const refreshProjects = useCallback(async () => {
    const response = await fetch(`${API_URL}/api/projects`);
    if (!response.ok) throw new Error("Could not load saved workspaces.");
    setProjects((await response.json()) as ProjectSummary[]);
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/health`);
      if (!response.ok) throw new Error("API health check failed.");
      setHealth((await response.json()) as Health);
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    void Promise.all([refreshProjects(), refreshHealth()]).catch(() => {
      setNotice("Backend is not connected yet. Start FastAPI on port 8000.");
    });
  }, [refreshHealth, refreshProjects]);

  const addNodeToCanvas = useCallback((kind: NodeKind, position?: { x: number; y: number }) => {
    const fallback = { x: 180 + (nodes.length % 3) * 300, y: 90 + (nodes.length % 4) * 170 };
    setNodes((current) => [...current, bindNode(createNode(kind, position ?? fallback))]);
  }, [bindNode, nodes.length, setNodes]);

  const addLibraryResource = useCallback((resource: LibraryResource, position?: { x: number; y: number }) => {
    let kind: NodeKind;
    let patch: Record<string, unknown>;
    if (resource.category === "tool") { kind = "tool"; patch = { resource_id: resource.resource_id, label: resource.label, arguments: {} }; }
    else if (resource.category === "skill") { kind = "tool"; patch = { resource_id: "tool:read_hermes_skill", label: resource.label, arguments: { skill_name: resource.metadata?.skill_name ?? resource.resource_id.slice(6) } }; }
    else if (resource.category === "agent") { kind = "agent"; patch = { target: resource.resource_id.slice(6), label: resource.label }; }
    else if (resource.category === "model") { kind = "coder"; patch = { provider: resource.provider, model: resource.model, label: resource.label }; }
    else if (resource.category === "runtime") { kind = "runtime"; patch = { profile_id: resource.metadata?.profile_id, label: resource.label }; }
    else { setNotice("Use Deploy template for template resources."); return; }
    const fallback = position ?? { x: 180 + (nodes.length % 3) * 300, y: 90 + (nodes.length % 4) * 170 };
    const node = createNode(kind, fallback);
    setNodes((current) => [...current, bindNode({ ...node, data: { ...node.data, ...patch } })]);
    setNotice(`Added ${resource.label} to the canvas.`);
  }, [bindNode, nodes.length, setNodes]);

  const runLibraryResource = useCallback(async (resource: LibraryResource, args: Record<string, unknown>, approved = false, previewId?: string) => {
    try {
      let preview: ApprovalPreview;
      if (previewId) preview = { preview_id: previewId, approvals: [], requires_approval: approved };
      else {
        const response = await fetch(`${API_URL}/api/actions/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resource_id: resource.resource_id, arguments: args }) });
        if (!response.ok) throw new Error(`Action preview failed (${response.status}).`);
        preview = await response.json() as ApprovalPreview;
        const normalizedArguments = preview.arguments ?? args;
        if (preview.requires_approval && !approved) { setPendingApproval({ ...preview, kind: "action", resource, arguments: normalizedArguments }); return; }
        args = normalizedArguments;
      }
      setNotice(`Running ${resource.label}…`);
      const response = await fetch(`${API_URL}/api/actions/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resource_id: resource.resource_id, arguments: args, preview_id: preview.preview_id, approved }) });
      const payload = await response.json() as { output?: string; detail?: string };
      if (!response.ok) throw new Error(payload.detail ?? `Action failed (${response.status}).`);
      setOutput(String(payload.output ?? "")); setRunStatus("complete"); setNotice(`${resource.label} completed.`);
    } catch (error) { setRunStatus("error"); setNotice(displayError(error)); }
  }, []);

  const deployTemplate = useCallback(async (resource: LibraryResource) => {
    try {
      const templateId = String(resource.metadata?.template_id ?? resource.resource_id.slice(9));
      const response = await fetch(`${API_URL}/api/templates/${encodeURIComponent(templateId)}/instantiate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ options: {} }) });
      if (!response.ok) throw new Error(`Template deployment failed (${response.status}).`);
      const payload = await response.json() as { graph: { nodes: CanvasNode[]; edges: Edge[] } };
      setNodes(payload.graph.nodes.map((node) => bindNode({ ...node, data: { ...nodeDefaults(node.type), ...node.data } })));
      setEdges(payload.graph.edges); setNotice(`Deployed ${resource.label}. Review the nodes, then Execute Flow.`);
    } catch (error) { setNotice(displayError(error)); }
  }, [bindNode, setEdges, setNodes]);

  const onPaletteDragStart = useCallback((event: DragEvent<HTMLButtonElement>, kind: NodeKind) => {
    event.dataTransfer.setData(NODE_MIME, kind);
    event.dataTransfer.effectAllowed = "move";
  }, []);

  const onDrop = useCallback((event: DragEvent) => {
    event.preventDefault();
    const resourceJson = event.dataTransfer.getData(RESOURCE_MIME);
    if (resourceJson && flowInstance) {
      try {
        const resource = JSON.parse(resourceJson) as LibraryResource;
        addLibraryResource(resource, flowInstance.screenToFlowPosition({ x: event.clientX, y: event.clientY }));
        return;
      } catch { setNotice("The dragged library resource was invalid."); return; }
    }
    const kind = event.dataTransfer.getData(NODE_MIME);
    if (!flowInstance || !isNodeKind(kind)) return;
    const position = flowInstance.screenToFlowPosition({ x: event.clientX, y: event.clientY });
    addNodeToCanvas(kind, position);
  }, [addLibraryResource, addNodeToCanvas, flowInstance]);

  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target) return;
    if (connection.source === connection.target) {
      setNotice("A node cannot connect to itself.");
      return;
    }
    setEdges((current) =>
      addEdge(
        {
          ...connection,
          id: `edge-${connection.source}-${connection.target}-${Date.now()}`,
          animated: true,
        },
        current,
      ),
    );
  }, [setEdges]);

  const saveWorkspace = useCallback(async () => {
    setRunStatus("saving");
    setNotice("Saving workspace graph to SQLite…");
    try {
      const body = {
        ...(projectId ? { id: projectId } : {}),
        name: projectName.trim() || "Untitled local workflow",
        canvas_state: serializedGraph(nodes as CanvasNode[], edges),
      };
      const response = await fetch(`${API_URL}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error("Workspace save failed.");
      const saved = (await response.json()) as ProjectResponse;
      setProjectId(saved.id);
      setSelectedProjectId(saved.id);
      setProjectName(saved.name);
      await refreshProjects();
      setRunStatus("complete");
      setNotice(`Saved ${saved.name}.`);
    } catch (error) {
      setRunStatus("error");
      setNotice(displayError(error));
    }
  }, [edges, nodes, projectId, projectName, refreshProjects]);

  const loadWorkspace = useCallback(async () => {
    if (!selectedProjectId) {
      setNotice("Choose a saved workspace first.");
      return;
    }
    try {
      const response = await fetch(`${API_URL}/api/projects/${selectedProjectId}`);
      if (!response.ok) throw new Error("Workspace load failed.");
      const payload = (await response.json()) as unknown;
      if (!isProjectResponse(payload)) throw new Error("Saved workspace data is invalid.");
      const saved = payload;
      const restored = saved.canvas_state.nodes.map((node) => {
        const kind = node.type;
        return bindNode({ ...node, type: kind, data: { ...nodeDefaults(kind), ...node.data } });
      });
      setNodes(restored);
      setEdges(saved.canvas_state.edges);
      setProjectId(saved.id);
      setProjectName(saved.name);
      setRunStatus("complete");
      setNotice(`Loaded ${saved.name}.`);
    } catch (error) {
      setRunStatus("error");
      setNotice(displayError(error));
    }
  }, [bindNode, selectedProjectId, setEdges, setNodes]);

  const validateWorkspace = useCallback(async () => {
    setRunStatus("validating");
    try {
      const response = await fetch(`${API_URL}/api/workflows/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ graph: serializedGraph(nodes as CanvasNode[], edges) }),
      });
      const data = (await response.json()) as { detail?: { errors?: string[] }; node_count?: number };
      if (!response.ok) throw new Error(data.detail?.errors?.join("; ") || "Graph validation failed.");
      setRunStatus("complete");
      setNotice(`Graph valid: ${data.node_count ?? 0} nodes ready.`);
      return true;
    } catch (error) {
      setRunStatus("error");
      setNotice(displayError(error));
      return false;
    }
  }, [edges, nodes]);

  const executeWorkspace = useCallback(async (approvalPreviewId?: string) => {
    const graph = serializedGraph(nodes as CanvasNode[], edges);
    try {
      if (approvalPolicy === "preflight" && !approvalPreviewId) {
        const previewResponse = await fetch(`${API_URL}/api/templates/preview-run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ graph }) });
        if (!previewResponse.ok) throw new Error(`Workflow review failed (${previewResponse.status}).`);
        const preview = await previewResponse.json() as ApprovalPreview;
        if (preview.requires_approval) { setPendingApproval({ ...preview, kind: "graph" }); return; }
        approvalPreviewId = preview.preview_id;
      }
      setRunStatus("running");
      setOutput("");
      setRunLines([{ id: `run-${Date.now()}`, kind: "system", text: "Creating durable local run…" }]);
      setNotice("Starting durable workflow…");
      const response = await fetch(`${API_URL}/api/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ graph, input_text: inputText, approval_preview_id: approvalPreviewId, approval_policy: approvalPolicy, retain_context: true, max_parallel: 4, ...(projectId ? { project_id: projectId } : {}) }),
      });
      const payload = await response.json() as { id?: string; status?: string; final_output?: string; detail?: string | { errors?: string[] } };
      if (!response.ok || !payload.id) {
        const detail = typeof payload.detail === "string" ? payload.detail : payload.detail?.errors?.join("; ") ?? `Workflow start failed (${response.status}).`;
        throw new Error(detail);
      }
      setActiveRunId(payload.id);
      setRunLines((current) => [...current, { id: payload.id!, kind: "system", text: `Durable run ${payload.id!.slice(0, 8)} · ${payload.status ?? "queued"}.` }]);
      setNotice(payload.status === "waiting_approval" || payload.status === "waiting_input" ? "Run is waiting in the Human-in-the-loop inspector." : "Run started; context is retained locally.");
    } catch (error) {
      setRunStatus("error");
      setNotice(displayError(error));
      setRunLines((current) => [...current, { id: `error-${current.length}`, kind: "error", text: displayError(error) }]);
    }
  }, [approvalPolicy, edges, inputText, nodes, projectId]);

  const handleDurableRunStatus = useCallback((value: string) => {
    if (value === "completed") { setRunStatus("complete"); setNotice("Workflow completed; full run context is retained locally."); }
    else if (value === "error" || value === "denied" || value === "cancelled") { setRunStatus("error"); setNotice(`Workflow ${value}.`); }
    else { setRunStatus("running"); setNotice(value === "waiting_approval" || value === "waiting_input" ? "Workflow is waiting for human input." : "Workflow is running."); }
  }, []);

  const statusLabel = useMemo(() => {
    if (runStatus === "running") return "RUNNING";
    if (runStatus === "saving") return "SAVING";
    if (runStatus === "validating") return "CHECKING";
    if (runStatus === "error") return "ERROR";
    if (runStatus === "complete") return "READY";
    return "IDLE";
  }, [runStatus]);

  const activeModel = health?.model_provider === "nanbeige"
    ? health.nanbeige_model
    : health?.model_provider === "lfm"
      ? health.lfm_model
    : health?.model_provider === "ollama"
      ? health.ollama_model
      : health?.minimax_model;
  const activeRouteReady = Boolean(health && (
    health.model_provider === "nanbeige"
      ? health.nanbeige_ready
      : health.model_provider === "lfm"
        ? health.lfm_ready
        : true
  ));
  const effectiveLeftCollapsed = leftPanelCollapsed && !stackedLayout;
  const effectiveRightCollapsed = rightPanelCollapsed && !stackedLayout;
  const workspaceStyle = {
    "--left-panel-width": `${effectiveLeftCollapsed ? 36 : leftPanelWidth}px`,
    "--right-panel-width": `${effectiveRightCollapsed ? 36 : rightPanelWidth}px`,
    "--left-splitter-width": effectiveLeftCollapsed ? "0px" : "7px",
    "--right-splitter-width": effectiveRightCollapsed ? "0px" : "7px",
  } as CSSProperties;

  return (
    <div className="workspace-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">M⊕</div>
          <div>
            <div className="brand-title">AI Visual Workspace</div>
            <div className="brand-subtitle">Local-first workflow composition</div>
          </div>
        </div>
        <div className={`health-pill ${activeRouteReady ? "health-ok" : "health-warn"}`}>
          <span className="health-dot" />
          {health ? `${health.model_provider} · ${activeModel}` : "API disconnected"}
        </div>
        <div className="top-actions">
          <input className="project-name-input" value={projectName} onChange={(event) => setProjectName(event.target.value)} aria-label="Workspace name" />
          <button className="button button-quiet" type="button" onClick={() => void saveWorkspace()}>Save Workspace</button>
          <select className="project-select" value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)} aria-label="Saved workspaces">
            <option value="">Load saved…</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <button className="button button-quiet" type="button" onClick={() => void loadWorkspace()}>Load Workspace</button>
          <button className="button button-primary" type="button" onClick={() => void executeWorkspace()}>Execute Flow <span className="button-arrow">↗</span></button>
        </div>
      </header>

      <div className="workspace-body" style={workspaceStyle}>
        {effectiveLeftCollapsed ? (
          <button className="panel-reopen panel-reopen-left" type="button" onClick={() => setLeftPanelCollapsed(false)} aria-label="Reopen left panel" title="Reopen library panel">›</button>
        ) : <aside className="left-panel panel-surface">
          <div className="panel-utility"><span>{Math.round(leftPanelWidth)} px</span><div><button type="button" onClick={resetPanelLayout}>Reset</button><button type="button" onClick={() => setLeftPanelCollapsed(true)} aria-label="Collapse left panel">‹</button></div></div>
          <LibraryPanel onAdd={addLibraryResource} onRun={(resource, args) => void runLibraryResource(resource, args)} onDeploy={(resource) => void deployTemplate(resource)} />
          <div className="panel-divider" />
          <div className="panel-heading">
            <div><span className="eyebrow">BUILD</span><h2>Node palette</h2></div>
            <span className="count-badge">{nodes.length}</span>
          </div>
          <p className="panel-copy">Drag a node into the canvas or click + to add it.</p>
          <div className="palette-list">
            {(Object.keys(NODE_META) as NodeKind[]).map((kind) => {
              const meta = NODE_META[kind];
              return (
                <button key={kind} className="palette-item" draggable onDragStart={(event) => onPaletteDragStart(event, kind)} onClick={() => addNodeToCanvas(kind)} type="button">
                  <span className={`palette-icon ${meta.accent}`}>{meta.icon}</span>
                  <span className="palette-text"><strong>{meta.label}</strong><small>{meta.hint}</small></span>
                  <span className="palette-add">+</span>
                </button>
              );
            })}
          </div>
          <div className="panel-divider" />
          <div className="mini-section-title">MODEL ROUTE</div>
          <div className="route-card"><span className="route-indicator nanbeige" /><div><strong>Nanbeige4.2-3B</strong><small>Shared RTX 2070 SUPER · :8080</small></div><span className="route-state">PRIMARY</span></div>
          <div className="route-card route-muted"><span className="route-indicator minimax" /><div><strong>LFM2.5-2.6B</strong><small>Explicit agent option · separate runtime</small></div><span className="route-state">OPT-IN</span></div>
          <div className="route-card route-muted"><span className="route-indicator minimax" /><div><strong>MiniMax-M3</strong><small>Explicit endpoint</small></div><span className="route-state">OPT-IN</span></div>
          <div className="route-card route-muted"><span className="route-indicator ollama" /><div><strong>Ollama</strong><small>Environment configured</small></div><span className="route-state">OPT-IN</span></div>
          <div className="panel-divider" />
          <div className="mini-section-title">HARDWARE LANES</div>
          <div className="hardware-row"><span className="hardware-chip gpu-purple">GPU 1</span><span>RTX 2070 Super</span><small>Nanbeige + STT</small></div>
          <div className="hardware-row"><span className="hardware-chip gpu-blue">GPU 0</span><span>RTX 5060 Ti</span><small>Available</small></div>
        </aside>}

        <div className={`panel-splitter panel-splitter-left${effectiveLeftCollapsed ? " is-hidden" : ""}`} role="separator" aria-label="Resize left panel" aria-orientation="vertical" tabIndex={effectiveLeftCollapsed ? -1 : 0} onPointerDown={(event) => beginPanelResize("left", event)} onKeyDown={(event) => resizePanelByKeyboard("left", event.key)}><span /></div>

        <main className="canvas-wrap" onDrop={onDrop} onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; }}>
          <div className="canvas-toolbar">
            <div className="canvas-title"><span className="live-pulse" />Workflow canvas <span className="canvas-meta">{nodes.length} nodes · {edges.length} connections</span></div>
            <div className="canvas-toolbar-actions"><button className="toolbar-button" type="button" onClick={() => void validateWorkspace()}>Validate</button><button className="toolbar-button" type="button" onClick={() => { setNodes([]); setEdges([]); setNotice("Canvas cleared."); }}>Clear</button></div>
          </div>
          <ReactFlow<CanvasNode, Edge>            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={setFlowInstance}
            fitView
            fitViewOptions={{ padding: 0.22 }}
            minZoom={0.25}
            maxZoom={1.5}
            attributionPosition="bottom-left"
          >
            <Background color="#263349" gap={22} size={1} />
            <Controls position="bottom-right" />
            <MiniMap nodeColor={(node) => NODE_META[(node.type as NodeKind) ?? "start"]?.accent === "node-coder" ? "#7c6cff" : "#2e4665"} maskColor="rgba(7, 12, 22, 0.72)" />
          </ReactFlow>
          {runLines.length > 0 && (
            <section className="terminal-overlay">
              <div className="terminal-header"><span><span className="terminal-dot" />Live execution</span><span className="terminal-status">{statusLabel}</span></div>
              <div className="terminal-lines">{runLines.slice(-8).map((line) => <div key={line.id} className={`terminal-line ${line.kind}`}><span className="terminal-prompt">›</span>{line.text}</div>)}</div>
            </section>
          )}
        </main>

        <div className={`panel-splitter panel-splitter-right${effectiveRightCollapsed ? " is-hidden" : ""}`} role="separator" aria-label="Resize right panel" aria-orientation="vertical" tabIndex={effectiveRightCollapsed ? -1 : 0} onPointerDown={(event) => beginPanelResize("right", event)} onKeyDown={(event) => resizePanelByKeyboard("right", event.key)}><span /></div>

        {effectiveRightCollapsed ? (
          <button className="panel-reopen panel-reopen-right" type="button" onClick={() => setRightPanelCollapsed(false)} aria-label="Reopen right panel" title="Reopen run panel">‹</button>
        ) : <aside className="right-panel panel-surface">
          <div className="panel-utility"><span>{Math.round(rightPanelWidth)} px</span><div><button type="button" onClick={resetPanelLayout}>Reset</button><button type="button" onClick={() => setRightPanelCollapsed(true)} aria-label="Collapse right panel">›</button></div></div>
          <div className="panel-heading"><div><span className="eyebrow">RUN CONTROL</span><h2>Input / output</h2></div><span className={`status-badge status-${runStatus}`}>{statusLabel}</span></div>
          <label className="control-label" htmlFor="workflow-input">Workflow input</label>
          <textarea id="workflow-input" className="control-textarea" value={inputText} onChange={(event) => setInputText(event.target.value)} rows={7} />
          <label className="control-label" htmlFor="approval-policy">Human-in-the-loop policy</label>
          <select id="approval-policy" className="control-select" value={approvalPolicy} onChange={(event) => setApprovalPolicy(event.target.value as typeof approvalPolicy)}><option value="preflight">Review protected actions before run</option><option value="per_action">Pause before each protected action</option><option value="step_through">Step through every node</option></select>
          <div className="control-actions"><button className="button button-primary full-width" type="button" onClick={() => void executeWorkspace()}>Execute Flow <span className="button-arrow">↗</span></button><button className="button button-quiet full-width" type="button" onClick={() => void validateWorkspace()}>Validate graph</button></div>
          <div className="panel-divider" />
          <div className="output-heading"><span className="eyebrow">FINAL OUTPUT</span><span className="output-lock">Local</span></div>
          <pre className="output-box">{output || "Output from the last run will appear here."}</pre>
          <div className="notice-box"><span className="notice-icon">i</span><span>{notice}</span></div>
          <div className="panel-divider" />
          <RunInspector activeRunId={activeRunId} onOutput={setOutput} onRunStatus={handleDurableRunStatus} />
          <div className="panel-divider" />
          <div className="mini-section-title">RUNTIME READINESS</div>
          <div className="readiness-list">
            <div><span className={health ? "ready-mark" : "warning-mark"}>{health ? "✓" : "!"}</span><span>FastAPI backend</span><small>{health ? "connected" : "offline"}</small></div>
            <div><span className={health?.nanbeige_ready ? "ready-mark" : "warning-mark"}>{health?.nanbeige_ready ? "✓" : "!"}</span><span>Nanbeige4.2 route</span><small>{health?.nanbeige_ready ? health.nanbeige_model : "listener offline"}</small></div>
            <div><span className={health?.lfm_ready ? "ready-mark" : "warning-mark"}>{health?.lfm_ready ? "✓" : "!"}</span><span>LFM2.5 route</span><small>{health?.lfm_ready ? health.lfm_model : "explicit option offline"}</small></div>
            <div><span className={health?.buzz_on_path ? "ready-mark" : "warning-mark"}>{health?.buzz_on_path ? "✓" : "!"}</span><span>Buzz CLI</span><small>{health?.buzz_on_path ? "available" : "not on PATH"}</small></div>
            <div><span className={health?.configured_agents?.length ? "ready-mark" : "warning-mark"}>{health?.configured_agents?.length ? "✓" : "!"}</span><span>Agent reactions</span><small>{health?.configured_agents?.length ? health.configured_agents.join(", ") : "none configured"}</small></div>
          </div>
          <div className="panel-divider" />
          <ChatPanel />
          <div className="panel-divider" />
          <ControlCenterPanel />
        </aside>}
      </div>
      {pendingApproval && <ApprovalReview
        title={pendingApproval.kind === "graph" ? "Approve workflow actions" : `Approve ${pendingApproval.resource.label}`}
        approvals={pendingApproval.approvals}
        onCancel={() => setPendingApproval(null)}
        onApprove={() => {
          const pending = pendingApproval;
          setPendingApproval(null);
          if (pending.kind === "graph") void executeWorkspace(pending.preview_id);
          else void runLibraryResource(pending.resource, pending.arguments, true, pending.preview_id);
        }}
      />}
    </div>
  );
}
