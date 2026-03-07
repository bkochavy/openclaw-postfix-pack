import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

type SuffixConfig = {
  marker?: string;
  separator?: string;
  providerAliases?: Record<string, string>;
  modelAliases?: Record<string, string>;
  providerFallbackLength?: number;
  modelFallbackLength?: number;
  identityMode?: "initial" | "full";
};

const DEFAULT_CONFIG: Required<SuffixConfig> = {
  marker: "ocstamp",
  separator: "\n",
  providerAliases: {
    "anthropic": "anK",
    "claude-cli": "anO",
    "codex-cli": "opK",
    "lmstudio": "lmL",
    "opencode": "ocK",
    "openai-codex": "opK",
    "openrouter": "orK",
    "vercel-ai-gateway": "veT",
    "xai": "xaK"
  },
  modelAliases: {
    "claude-haiku-4.5": "h45",
    "claude-haiku-4-5": "h45",
    "claude-opus-4.6": "o46",
    "claude-opus-4-6": "o46",
    "claude-sonnet-4.5": "s45",
    "claude-sonnet-4-5": "s45",
    "claude-sonnet-4.6": "s46",
    "claude-sonnet-4-6": "s46",
    "glm-5": "g5",
    "gpt-5.2": "gpt52",
    "gpt-5.3-codex": "gpt53c",
    "gpt-5.3-codex-spark": "gpt53s",
    "gpt-5.4": "gpt54",
    "grok-4-1-fast": "g41f",
    "haiku-4.6": "h46",
    "kimi-k2.5": "k25",
    "minimax-m2.5": "m25",
    "opus-4.6": "o46",
    "qwen3-8b-mlx": "q38b",
    "sonnet-4.6": "s46"
  },
  providerFallbackLength: 3,
  modelFallbackLength: 12,
  identityMode: "initial"
};

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function sanitizeToken(value: string, fallbackLength: number): string {
  const normalized = value.toLowerCase().replace(/[^a-z0-9]+/g, "");
  return normalized.slice(0, Math.max(1, fallbackLength)) || "unk";
}

function normalizeModel(value: string): string {
  const slash = value.lastIndexOf("/");
  const raw = slash >= 0 ? value.slice(slash + 1) : value;
  return raw.replace(/-\d{8}$/, "").replace(/-latest$/, "");
}

function normalizeIdentity(value: string, mode: "initial" | "full"): string {
  const trimmed = value.trim();
  if (!trimmed) return "?";
  if (mode === "full") return trimmed;
  return trimmed.slice(0, 1).toUpperCase();
}

function resolveConfig(raw: Record<string, unknown> | undefined): Required<SuffixConfig> {
  const providerAliases = {
    ...DEFAULT_CONFIG.providerAliases,
    ...(raw?.providerAliases && typeof raw.providerAliases === "object" ? raw.providerAliases as Record<string, string> : {})
  };
  const modelAliases = {
    ...DEFAULT_CONFIG.modelAliases,
    ...(raw?.modelAliases && typeof raw.modelAliases === "object" ? raw.modelAliases as Record<string, string> : {})
  };
  return {
    marker: typeof raw?.marker === "string" && raw.marker.trim() ? raw.marker.trim() : DEFAULT_CONFIG.marker,
    separator: typeof raw?.separator === "string" ? raw.separator : DEFAULT_CONFIG.separator,
    providerAliases,
    modelAliases,
    providerFallbackLength: typeof raw?.providerFallbackLength === "number" ? Math.max(1, Math.floor(raw.providerFallbackLength)) : DEFAULT_CONFIG.providerFallbackLength,
    modelFallbackLength: typeof raw?.modelFallbackLength === "number" ? Math.max(1, Math.floor(raw.modelFallbackLength)) : DEFAULT_CONFIG.modelFallbackLength,
    identityMode: raw?.identityMode === "full" ? "full" : DEFAULT_CONFIG.identityMode
  };
}

export default function register(api: OpenClawPluginApi): void {
  const config = resolveConfig((api.pluginConfig ?? {}) as Record<string, unknown>);
  const markerRe = new RegExp(`^\\[\\[${escapeRegExp(config.marker)}:([^:\\]]+):([^:\\]]+):([^\\]]+)\\]\\]\\s*`);

  api.on("message_sending", (event) => {
    const match = markerRe.exec(event.content);
    if (!match) return;

    const [, rawProvider, rawModel, rawIdentity] = match;
    const body = event.content.slice(match[0].length).trimStart();
    if (!body.trim()) return { content: event.content };

    const provider = rawProvider.trim();
    const model = normalizeModel(rawModel.trim());
    const identity = normalizeIdentity(rawIdentity, config.identityMode);

    const providerAlias = config.providerAliases[provider] ?? sanitizeToken(provider, config.providerFallbackLength);
    const modelAlias = config.modelAliases[model] ?? sanitizeToken(model, config.modelFallbackLength);
    const stamp = `${providerAlias}/${modelAlias}@${identity}`;
    const suffix = `${config.separator}${stamp}`;
    const content = body.endsWith(suffix) || body.endsWith(stamp) ? body : `${body}${suffix}`;

    api.logger.debug?.(`message-stamp-suffix: ${provider}/${model} -> ${stamp}`);
    return { content };
  });
}
