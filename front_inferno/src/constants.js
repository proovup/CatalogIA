export const PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "mistral", label: "Mistral AI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "bedrock", label: "AWS Bedrock" },
];

export const MODELS = {
  openai: ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
  mistral: ["mistral-large-latest", "mistral-medium", "mistral-small"],
  anthropic: ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
  bedrock: ["anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-haiku-20240307-v1:0"],
};

export const DEFAULT_PROVIDER = "mistral";
export const DEFAULT_MODEL = "mistral-large-latest";
