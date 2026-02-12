// Backend API configuration
export const API_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000/api/v1";

export const WS_URL =
  import.meta.env.VITE_WS_URL || "ws://localhost:8000/api/v1/ws";

// Keyboard simulation toggle (default: enabled for development)
export const ENABLE_KEYBOARD_SIM =
  import.meta.env.VITE_ENABLE_KEYBOARD_SIM !== "false";
