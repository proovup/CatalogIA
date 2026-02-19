const BASE = "/api/v1";

function toErrorMessage(detail, fallback = "Request failed") {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const path = Array.isArray(item.loc) ? item.loc.join(".") : "";
          const msg = item.msg || JSON.stringify(item);
          return path ? `${path}: ${msg}` : msg;
        }
        return String(item);
      })
      .join(" | ");
  }
  if (typeof detail === "object") {
    return detail.message || detail.msg || JSON.stringify(detail);
  }
  return String(detail);
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(toErrorMessage(err.detail, res.statusText));
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Documents
  listDocuments: () => request("/products/documents"),
  uploadDocument: (file, supplierId) => {
    const form = new FormData();
    form.append("file", file);
    if (supplierId) form.append("supplier_id", supplierId);
    return fetch(`${BASE}/documents/upload`, { method: "POST", body: form }).then((r) => {
      if (!r.ok) throw new Error("Upload failed");
      return r.json();
    });
  },

  // Products
  listProducts: (params = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status_filter", params.status);
    if (params.supplier_id) qs.set("supplier_id", params.supplier_id);
    if (params.search) qs.set("search", params.search);
    if (params.skip) qs.set("skip", params.skip);
    if (params.limit) qs.set("limit", params.limit);
    return request(`/products/?${qs}`);
  },
  getProductStats: () => request("/products/stats"),
  getProduct: (id) => request(`/products/${id}`),
  updateProduct: (id, data) =>
    request(`/products/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteProduct: (id) => request(`/products/${id}`, { method: "DELETE" }),

  // Analyze document sheets (for human verification before extraction)
  analyzeDocument: (documentId, provider = "openai") =>
    request("/products/analyze", {
      method: "POST",
      body: JSON.stringify({
        document_id: documentId,
        provider,
      }),
    }),

  // Extraction (returns { job_id, status })
  extractProducts: (
    documentId,
    formatName = "default",
    analysis = null,
    options = {},
  ) =>
    request("/products/extract", {
      method: "POST",
      body: JSON.stringify({
        document_id: documentId,
        format_name: formatName,
        analysis,
        field_mapping_override: options.field_mapping_override || null,
        max_products: Number.isInteger(options.max_products) ? options.max_products : null,
        source_mode: options.source_mode || "document",
        presented_mode: options.presented_mode || "docling_ocr",
        provider: options.provider || null,
        model_name: options.model_name || null,
      }),
    }),

  extractWebsiteProducts: (payload) =>
    request("/products/extract/website", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // SSE progress stream for extraction job
  streamExtractionProgress: (jobId, onEvent, onDone, onError) => {
    const es = new EventSource(`${BASE}/products/extract/${jobId}/progress`);
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onEvent(data);
        if (data.done) {
          es.close();
          if (data.status === "error") {
            onError(data.error || "Extraction failed");
          } else {
            onDone(data);
          }
        }
      } catch { }
    };
    es.onerror = () => {
      es.close();
      onError("Connection lost");
    };
    return es;
  },

  // Classification
  classifyProduct: (productId, provider = "openai", modelName = null) =>
    request(`/products/${productId}/classify`, {
      method: "POST",
      body: JSON.stringify({ provider, model_name: modelName }),
    }),

  // Regeneration
  regenerateProduct: (productId, formatName = "default", provider = "openai", modelName = null) =>
    request(`/products/${productId}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ format_name: formatName, provider, model_name: modelName }),
    }),
  regenerateField: (productId, data) =>
    request(`/products/${productId}/regenerate-field`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Formats (legacy filesystem)
  listFormatsLegacy: () => request("/products/formats"),

  // Formats (DB)
  listFormats: () => request("/formats/"),
  createFormat: (data) =>
    request("/formats/", { method: "POST", body: JSON.stringify(data) }),
  uploadFormat: (file) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${BASE}/formats/upload`, { method: "POST", body: form }).then((r) => {
      if (!r.ok) throw new Error("Upload format failed");
      return r.json();
    });
  },
  getFormat: (id) => request(`/formats/${id}`),
  updateFormat: (id, data) =>
    request(`/formats/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteFormat: (id) => request(`/formats/${id}`, { method: "DELETE" }),

  // Suppliers
  listSuppliers: (params = {}) => {
    const qs = new URLSearchParams();
    if (params.active_only) qs.set("active_only", "true");
    if (params.skip) qs.set("skip", params.skip);
    if (params.limit) qs.set("limit", params.limit);
    return request(`/suppliers/?${qs}`);
  },
  createSupplier: (data) =>
    request("/suppliers/", { method: "POST", body: JSON.stringify(data) }),
  getSupplier: (id) => request(`/suppliers/${id}`),
  updateSupplier: (id, data) =>
    request(`/suppliers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteSupplier: (id) => request(`/suppliers/${id}`, { method: "DELETE" }),
  getSupplierDocuments: (id) => request(`/suppliers/${id}/documents`),

  // Scraping
  scrapeProduct: (productId, data) =>
    request(`/scraping/${productId}/scrape`, { method: "POST", body: JSON.stringify(data) }),
  getScrapeResults: (productId) => request(`/scraping/${productId}/scrape-results`),
  getScrapeResult: (productId, resultId) => request(`/scraping/${productId}/scrape-results/${resultId}`),
  deleteScrapeResult: (productId, resultId) =>
    request(`/scraping/${productId}/scrape-results/${resultId}`, { method: "DELETE" }),

  // Gallery
  getProductGallery: (productId) => request(`/scraping/${productId}/gallery`),
  downloadGalleryImages: (productId, imageUrls) =>
    fetch(`${BASE}/scraping/${productId}/gallery/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_urls: imageUrls }),
    }).then((r) => {
      if (!r.ok) throw new Error("Download failed");
      return r.blob();
    }),

  // Proxy image (returns URL string for <img> src)
  proxyImageUrl: (url) => `${BASE}/scraping/proxy-image?url=${encodeURIComponent(url)}`,

  // Enrichment
  uploadEnrichmentDocument: (file, enrichmentType = "other") => {
    const form = new FormData();
    form.append("file", file);
    form.append("enrichment_type", enrichmentType);
    return fetch(`${BASE}/enrichment/upload`, { method: "POST", body: form }).then((r) => {
      if (!r.ok) throw new Error("Upload failed");
      return r.json();
    });
  },
  processEnrichment: (documentId, productIds, enrichmentType = "other", options = {}) =>
    request("/enrichment/process", {
      method: "POST",
      body: JSON.stringify({
        document_id: documentId,
        product_ids: productIds,
        enrichment_type: enrichmentType,
        provider: options.provider || null,
        model_name: options.model_name || null,
      }),
    }),
  streamEnrichmentProgress: (jobId, onEvent, onDone, onError) => {
    const es = new EventSource(`${BASE}/enrichment/${jobId}/progress`);
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onEvent(data);
        if (data.done) {
          es.close();
          if (data.status === "error") {
            onError(data.error || "Enrichment failed");
          } else {
            onDone(data);
          }
        }
      } catch { }
    };
    es.onerror = () => {
      es.close();
      onError("Connection lost");
    };
    return es;
  },
  listEnrichmentDocuments: (productId) => {
    const qs = productId ? `?product_id=${productId}` : "";
    return request(`/enrichment/documents${qs}`);
  },
  getEnrichmentDocument: (id) => request(`/enrichment/documents/${id}`),
  deleteEnrichmentDocument: (id) =>
    request(`/enrichment/documents/${id}`, { method: "DELETE" }),
  getProductEnrichments: (productId) =>
    request(`/enrichment/product/${productId}`),

  // Config
  getConfig: () => request("/config/"),
};
