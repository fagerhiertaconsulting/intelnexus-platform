export type EntityType =
  | "person"
  | "organization"
  | "domain"
  | "ip"
  | "email"
  | "phone"
  | "username"
  | "crypto_wallet"
  | "location"
  | "document"
  | "incident";

export interface ProvenanceRecord {
  source_url: string;
  timestamp: string;
  sha256: string;
  collector_plugin: string;
  note?: string;
}

export interface Entity {
  id: string;
  type: EntityType;
  name: string;
  aliases: string[];
  attributes: Record<string, any>;
  provenance: ProvenanceRecord[];
  confidence_score: number;
  case_id?: string;
  created_at: string;
  updated_at: string;
}

export interface Relationship {
  id: string;
  source_id: string;
  target_id: string;
  relation_type: string;
  attributes: Record<string, any>;
  provenance: ProvenanceRecord[];
  confidence_score: number;
  case_id?: string;
  created_at: string;
}

export interface Case {
  id: string;
  title: string;
  description: string;
  status: "active" | "suspended" | "closed" | "archived";
  priority: "low" | "medium" | "high" | "critical";
  tags: string[];
  investigator: string;
  created_at: string;
  updated_at: string;
}

export interface EvidenceItem {
  id: string;
  case_id: string;
  title: string;
  file_path: string;
  file_size_bytes: number;
  mime_type: string;
  sha256: string;
  source_url?: string;
  collector_plugin?: string;
  metadata: Record<string, any>;
  recorded_at: string;
}

export interface GraphNode {
  id: string;
  data: {
    id: string;
    label: string;
    type: EntityType;
    aliases: string[];
    confidence_score: number;
    attributes: Record<string, any>;
    created_at?: string;
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  data: {
    id: string;
    source: string;
    target: string;
    label: string;
    relation_type: string;
    confidence_score: number;
    attributes: Record<string, any>;
  };
}

export interface GraphData {
  case_id: string;
  node_count: number;
  edge_count: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface InfluencerNode {
  id: string;
  name: string;
  type: string;
  score: number;
  pagerank: number;
  betweenness: number;
  degree: number;
}

export interface GraphMetrics {
  degree: Record<string, number>;
  in_degree: Record<string, number>;
  out_degree: Record<string, number>;
  betweenness: Record<string, number>;
  pagerank: Record<string, number>;
  top_influencers: InfluencerNode[];
}

export interface TransformInfo {
  name: string;
  display_name: string;
  description: string;
  category: string;
  supported_types?: string[];
  required_credentials?: string[];
  is_available?: boolean;
  is_byoak?: boolean;
}

export interface MatchCandidate {
  primary_entity_id: string;
  secondary_entity_id: string;
  primary_name: string;
  secondary_name: string;
  match_type: "deterministic" | "probabilistic";
  confidence: number;
  reasons: string[];
}

export interface CustodyAudit {
  case_id: string;
  total_items: number;
  valid_count: number;
  tampered_count: number;
  missing_count: number;
  chain_of_custody_intact: boolean;
  verified_items: Array<{ id: string; title: string; sha256: string; status: string }>;
  tampered_items: Array<{ id: string; title: string; status: string }>;
  missing_items: Array<{ id: string; title: string; status: string }>;
}

// --- V2 PERSONAS & BYOAK TYPES ---

export interface WorkspaceRole {
  role_id: string;
  display_name: string;
  description: string;
  target_audience: string;
  icon_name: string;
  theme: string;
  default_view: "wizard" | "graph" | "document" | "dossier" | "financial" | "map";
  active_widgets: string[];
  suggested_api_keys: Array<{ key_name: string; label: string }>;
  default_playbooks: Array<{ id: string; title: string; description: string }>;
}

export interface VaultKey {
  key_name: string;
  service: string;
  label: string;
  domain: string;
  description: string;
  requires_paid: boolean;
  is_configured: boolean;
  masked_value: string | null;
  updated_at: string | null;
}

export interface DatingVerificationResult {
  target_name: string;
  overall_verdict: string;
  risk_level: "LOW" | "WARNING" | "CRITICAL";
  risk_score_pct: number;
  risk_factors: string[];
  recommended_action: string;
  catfish_check: {
    detected: boolean;
    source?: string;
  };
  phone_check: {
    checked: boolean;
    is_voip: boolean;
    carrier?: string;
  };
  profiles_found: number;
}
