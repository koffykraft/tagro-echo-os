// Deploy-time configuration. Keep apiBaseUrl blank for fully working single-device IndexedDB mode.
// For Cloudflare/AWS set it to the deployed API base, e.g. https://api.example.com/api
window.TAGRO_CONFIG = {
  apiBaseUrl: "",
  tenantId: "tagro",
  brand: "TAGRO STIHL",
  allowOwnerNegativeStockOverride: true,
  currency: "INR"
};
