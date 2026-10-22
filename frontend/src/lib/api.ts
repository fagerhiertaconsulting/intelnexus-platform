import {
  Case,
  Entity,
  Relationship,
  EvidenceItem,
  GraphData,
  GraphMetrics,
  TransformInfo,
  TransformDryRunEstimate,
  MatchCandidate,
  CustodyAudit,
  WorkspaceRole,
  VaultKey,
  DatingVerificationResult,
  TwoFactorStatus,
  SecurityKeyItem,
  TOTPGenerateData,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const requiresStepUp =
      res.status === 403 &&
      (res.headers.get("x-require-step-up") === "true" ||
        res.headers.get("X-Require-Step-Up") === "true");

    let errDetail = "API förfrågan misslyckades";
    try {
      const err = await res.json();
      errDetail = err.detail || JSON.stringify(err);
    } catch {
      errDetail = await res.text();
    }

    const errorObj = new Error(errDetail) as any;
    errorObj.status = res.status;
    errorObj.requiresStepUp = requiresStepUp;

    if (requiresStepUp && typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("openintel:require-step-up", {
          detail: { endpoint, message: errDetail },
        })
      );
    }

    throw errorObj;
  }

  return res.json();
}


export const api = {
  // Cases
  listCases: () => request<Case[]>("/api/cases"),
  getCase: (id: string) => request<Case>(`/api/cases/${id}`),
  createCase: (data: Partial<Case>) =>
    request<Case>("/api/cases", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateCase: (id: string, data: Partial<Case>) =>
    request<Case>(`/api/cases/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteCase: (id: string) =>
    request<{ message: string }>(`/api/cases/${id}`, {
      method: "DELETE",
    }),
  getCaseStats: (id: string) => request<any>(`/api/cases/${id}/stats`),

  // Entities & Relationships
  listEntities: (caseId?: string, type?: string) => {
    const params = new URLSearchParams();
    if (caseId) params.append("case_id", caseId);
    if (type) params.append("entity_type", type);
    return request<Entity[]>(`/api/entities?${params.toString()}`);
  },
  getEntity: (id: string) => request<Entity>(`/api/entities/${id}`),
  createEntity: (data: any) =>
    request<Entity>("/api/entities", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteEntity: (id: string) =>
    request<{ message: string }>(`/api/entities/${id}`, {
      method: "DELETE",
    }),
  listRelationships: (caseId?: string) => {
    const params = new URLSearchParams();
    if (caseId) params.append("case_id", caseId);
    return request<Relationship[]>(`/api/entities/relationships?${params.toString()}`);
  },
  createRelationship: (data: any) =>
    request<Relationship>("/api/entities/relationships", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteRelationship: (id: string) =>
    request<{ message: string }>(`/api/entities/relationships/${id}`, {
      method: "DELETE",
    }),

  // Entity Resolution
  findMatches: (caseId: string, threshold = 0.85) =>
    request<MatchCandidate[]>(`/api/entities/resolution/matches/${caseId}?threshold=${threshold}`),
  mergeEntities: (primaryId: string, secondaryId: string, caseId: string) =>
    request<Entity>("/api/entities/resolution/merge", {
      method: "POST",
      body: JSON.stringify({ primary_id: primaryId, secondary_id: secondaryId, case_id: caseId }),
    }),

  // Transforms
  listTransforms: () => request<TransformInfo[]>("/api/transforms"),
  dryRunTransform: (transformName: string, targetId: string) =>
    request<TransformDryRunEstimate>("/api/v1/transforms/dry-run", {
      method: "POST",
      body: JSON.stringify({ transform_name: transformName, target_id: targetId }),
    }),
  getTransformsForEntity: (entityId: string) =>
    request<{ entity_id: string; name: string; type: string; available_transforms: TransformInfo[] }>(
      `/api/transforms/for-entity/${entityId}`
    ),
  executeTransform: (transformName: string, entityId: string, options = {}) =>
    request<any>("/api/transforms/execute", {
      method: "POST",
      body: JSON.stringify({ transform_name: transformName, entity_id: entityId, options }),
    }),
  executeBatchTransforms: (transformNames: string[], entityId: string, options = {}) =>
    request<any[]>("/api/transforms/execute-batch", {
      method: "POST",
      body: JSON.stringify({ transform_names: transformNames, entity_id: entityId, options }),
    }),

  // Graph
  getGraph: (caseId: string) => request<GraphData>(`/api/graph/${caseId}`),
  getGraphMetrics: (caseId: string) => request<GraphMetrics>(`/api/graph/${caseId}/metrics`),
  getEgoGraph: (caseId: string, nodeId: string, radius = 1) =>
    request<GraphData>(`/api/graph/${caseId}/ego/${nodeId}?radius=${radius}`),
  getShortestPath: (caseId: string, sourceId: string, targetId: string) =>
    request<{ found: boolean; path: string[]; hop_count?: number }>(
      `/api/graph/${caseId}/shortest-path?source_id=${sourceId}&target_id=${targetId}`
    ),

  // Evidence
  listEvidence: (caseId?: string) => {
    const params = new URLSearchParams();
    if (caseId) params.append("case_id", caseId);
    return request<EvidenceItem[]>(`/api/evidence?${params.toString()}`);
  },
  getEvidence: (id: string) => request<EvidenceItem>(`/api/evidence/${id}`),
  createWebSnapshot: (url: string, caseId: string, title?: string) =>
    request<EvidenceItem>("/api/evidence/snapshot", {
      method: "POST",
      body: JSON.stringify({ url, case_id: caseId, title }),
    }),
  auditCustody: (caseId: string) => request<CustodyAudit>(`/api/evidence/audit/${caseId}`),

  // AI & Analysis
  extractNer: (text: string, caseId: string, autoCommit = false) =>
    request<{ case_id: string; extracted_count: number; entities: Entity[] }>("/api/analysis/ner", {
      method: "POST",
      body: JSON.stringify({ text, case_id: caseId, auto_commit_to_case: autoCommit }),
    }),
  getMarkdownReportUrl: (caseId: string, mode: string = "full", locale: string = "sv") =>
    `${API_BASE}/api/analysis/report/${caseId}/markdown?mode=${encodeURIComponent(mode)}&locale=${encodeURIComponent(locale)}`,
  getHtmlReportUrl: (caseId: string, mode: string = "full", locale: string = "sv") =>
    `${API_BASE}/api/analysis/report/${caseId}/html?mode=${encodeURIComponent(mode)}&locale=${encodeURIComponent(locale)}`,

  // --- V2 ROLES, WORKSPACES & PLAYBOOKS ---
  listRoles: () => request<WorkspaceRole[]>("/api/roles"),
  getRole: (roleId: string) => request<WorkspaceRole>(`/api/roles/${roleId}`),

  // Vault (BYOAK)
  listVaultKeys: () => request<VaultKey[]>("/api/vault"),
  storeVaultKey: (keyName: string, apiKey: string, label?: string) =>
    request<{ status: string; message: string }>("/api/vault", {
      method: "POST",
      body: JSON.stringify({ key_name: keyName, api_key: apiKey, label }),
    }),
  deleteVaultKey: (keyName: string) =>
    request<{ status: string; message: string }>(`/api/vault/${keyName}`, {
      method: "DELETE",
    }),
  testVaultKey: (keyName: string) => request<any>(`/api/vault/test/${keyName}`, { method: "POST" }),

  // Playbooks
  runDatingVerification: (data: {
    case_id: string;
    name: string;
    phone?: string;
    email?: string;
    image_url?: string;
    story?: string;
  }) =>
    request<DatingVerificationResult>("/api/playbooks/dating-verification", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  sanitizeWhistleblowerMedia: async (caseId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/api/playbooks/whistleblower-sanitize?case_id=${caseId}`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      throw new Error("Kunde inte sanera fil");
    }
    return res.json();
  },

  // --- 2FA & SECURITY ---
  get2FAStatus: () => request<TwoFactorStatus>("/api/auth/2fa/status"),
  listSecurityKeys: () => request<SecurityKeyItem[]>("/api/auth/2fa/keys"),
  deleteSecurityKey: (keyId: string) =>
    request<{ status: string; message: string }>(`/api/auth/2fa/keys/${keyId}`, {
      method: "DELETE",
    }),
  getWebAuthnRegOptions: () =>
    request<any>("/api/auth/2fa/webauthn/register-options", { method: "POST" }),
  verifyWebAuthnRegistration: (data: { key_name: string; credential: any }) =>
    request<{ status: string; message: string; backup_codes?: string[] }>(
      "/api/auth/2fa/webauthn/register-verify",
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),
  getWebAuthnAuthOptions: () =>
    request<any>("/api/auth/2fa/webauthn/auth-options", { method: "POST" }),
  verifyWebAuthnAuth: (credential: any) =>
    request<{ status: string; message: string; is_elevated: boolean; elevated_until: string }>(
      "/api/auth/2fa/webauthn/auth-verify",
      {
        method: "POST",
        body: JSON.stringify({ credential }),
      }
    ),
  generateTOTPSecret: () => request<TOTPGenerateData>("/api/auth/2fa/totp/generate", { method: "POST" }),
  enableTOTP: (code: string) =>
    request<{ status: string; message: string; backup_codes?: string[] }>("/api/auth/2fa/totp/enable", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  disableTOTP: () => request<{ status: string; message: string }>("/api/auth/2fa/totp/disable", { method: "POST" }),
  verifyBackupCode: (code: string) =>
    request<{ status: string; message: string; is_elevated: boolean; elevated_until: string; remaining_backup_codes: number }>(
      "/api/auth/2fa/backup-codes/verify",
      {
        method: "POST",
        body: JSON.stringify({ code }),
      }
    ),
  regenerateBackupCodes: () =>
    request<{ status: string; message: string; backup_codes: string[] }>("/api/auth/2fa/backup-codes/regenerate", {
      method: "POST",
    }),
  stepUpVerify: (data: { method: "totp" | "webauthn" | "backup_code"; code?: string; credential?: any }) =>
    request<{ status: string; message: string; is_elevated: boolean; elevated_until: string }>(
      "/api/auth/2fa/step-up/verify",
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),
  toggleStepUpVault: (required: boolean) =>
    request<{ status: string; message: string; step_up_vault_required: boolean }>(
      "/api/auth/2fa/step-up/toggle-vault",
      {
        method: "POST",
        body: JSON.stringify({ step_up_vault_required: required }),
      }
    ),
  disableAll2FA: () =>
    request<{ status: string; message: string; is_2fa_enabled: boolean }>("/api/auth/2fa/disable", {
      method: "POST",
    }),
};

